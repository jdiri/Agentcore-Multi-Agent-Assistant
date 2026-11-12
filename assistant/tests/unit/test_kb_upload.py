import json
from pathlib import Path

import pytest

from support.kb_metadata import split_corpus
from support.kb_upload import existing_keys, normalise_prefix, plan_upload, upload

KB_DIR = Path(__file__).resolve().parents[2] / "Project3-Corpus-Documents/p3-corpus/knowledge-base"


class FakeS3:
    """In-memory stand-in for the boto3 S3 client; `page_size` forces pagination."""

    def __init__(self, objects: dict[str, bytes] | None = None, page_size: int = 1000):
        self.objects = dict(objects or {})
        self.page_size = page_size
        self.puts: list[dict] = []

    def put_object(self, *, Bucket, Key, Body, ContentType):  # noqa: N803 (boto3 names)
        self.puts.append({"Bucket": Bucket, "Key": Key, "ContentType": ContentType})
        self.objects[Key] = Body

    def list_objects_v2(self, *, Bucket, Prefix, ContinuationToken=None):  # noqa: N803
        keys = sorted(k for k in self.objects if k.startswith(Prefix))
        start = int(ContinuationToken or 0)
        page = keys[start : start + self.page_size]
        response = {"Contents": [{"Key": k} for k in page]}
        if start + self.page_size < len(keys):
            response |= {"IsTruncated": True, "NextContinuationToken": str(start + self.page_size)}
        return response

    def delete_object(self, *, Bucket, Key):  # noqa: N803
        del self.objects[Key]


@pytest.fixture(scope="module")
def chunks():
    return split_corpus(KB_DIR)


# 1. Prefix handling.


@pytest.mark.parametrize("prefix", ["chunks", "chunks/", "/chunks/", " chunks "])
def test_prefix_is_normalised(prefix):
    assert normalise_prefix(prefix) == "chunks/"


@pytest.mark.parametrize("prefix", ["", "/", "  "])
def test_empty_prefix_refused(prefix):
    with pytest.raises(ValueError, match="prefix is required"):
        normalise_prefix(prefix)


# 2. The upload plan.


def test_two_files_per_chunk(chunks):
    files = plan_upload(chunks, "chunks/")
    assert len(files) == 2 * len(chunks) == 240
    assert all(file.key.startswith("chunks/") for file in files)


def test_sidecar_sits_next_to_its_chunk(chunks):
    keys = {file.key for file in plan_upload(chunks, "chunks/")}
    for chunk in chunks:
        assert f"chunks/{chunk.name}" in keys
        assert f"chunks/{chunk.name}.metadata.json" in keys


def test_planned_sidecar_body_is_bedrock_json(chunks):
    files = {f.key: f for f in plan_upload(chunks, "chunks/")}
    sidecar = files["chunks/account-transfer-policy-v3.1__s4.md.metadata.json"]
    assert sidecar.content_type == "application/json"
    attributes = json.loads(sidecar.body)["metadataAttributes"]
    assert attributes["superseded"] is True and attributes["section"] == "4"


def test_planned_chunk_body_is_utf8_text(chunks):
    files = {f.key: f for f in plan_upload(chunks, "chunks/")}
    chunk = files["chunks/account-transfer-policy-v3.2__s4.md"]
    assert chunk.content_type == "text/markdown; charset=utf-8"
    assert chunk.body.decode("utf-8").startswith("Account Transfer Policy v3.2 — 4. Timelines")


def test_duplicate_keys_refused(chunks):
    with pytest.raises(ValueError, match="same S3 key"):
        plan_upload([chunks[0], chunks[0]], "chunks/")


# 3. Uploading to a fake S3.


def test_upload_puts_every_file(chunks):
    s3 = FakeS3()
    report = upload(s3, "bucket", "chunks/", chunks)
    assert len(s3.puts) == 240 and len(report.uploaded) == 240
    assert {put["Bucket"] for put in s3.puts} == {"bucket"}
    assert report.stale == () and report.deleted == ()


def test_upload_twice_is_harmless(chunks):
    s3 = FakeS3()
    upload(s3, "bucket", "chunks/", chunks)
    report = upload(s3, "bucket", "chunks/", chunks)
    assert len(s3.objects) == 240 and report.stale == ()


def test_stale_files_reported_not_deleted(chunks):
    s3 = FakeS3({"chunks/old__s9.md": b"x", "chunks/old__s9.md.metadata.json": b"{}"})
    report = upload(s3, "bucket", "chunks/", chunks)
    assert report.stale == ("chunks/old__s9.md", "chunks/old__s9.md.metadata.json")
    assert report.deleted == ()
    assert "chunks/old__s9.md" in s3.objects


def test_stale_files_deleted_when_asked(chunks):
    s3 = FakeS3({"chunks/old__s9.md": b"x"})
    report = upload(s3, "bucket", "chunks/", chunks, delete_stale=True)
    assert report.deleted == ("chunks/old__s9.md",)
    assert "chunks/old__s9.md" not in s3.objects


def test_files_outside_the_prefix_are_untouched(chunks):
    # The 18 original documents at the bucket's top level must never be listed or deleted.
    s3 = FakeS3({"account-transfer-policy-v3.2.md": b"original"})
    report = upload(s3, "bucket", "chunks/", chunks, delete_stale=True)
    assert report.stale == ()
    assert s3.objects["account-transfer-policy-v3.2.md"] == b"original"


def test_listing_follows_pagination():
    s3 = FakeS3({f"chunks/{n}.md": b"" for n in range(5)}, page_size=2)
    assert existing_keys(s3, "bucket", "chunks/") == {f"chunks/{n}.md" for n in range(5)}
