"""Upload KB chunks and their `.metadata.json` sidecars to S3 for the Bedrock data source.

Takes the S3 client as an argument so unit tests can pass a fake; only `loaders/upload_kb.py`
creates a real boto3 client. Files already under the prefix that are no longer produced
("stale") are reported and only deleted when asked: Bedrock would otherwise keep indexing them.
"""

import json
from dataclasses import dataclass
from typing import Any, Protocol

from .kb_metadata import KBChunk, chunk_sidecar, sidecar_name


class S3Client(Protocol):
    """The three boto3 S3 calls this module uses."""

    def put_object(self, **kwargs: Any) -> Any: ...
    def list_objects_v2(self, **kwargs: Any) -> Any: ...
    def delete_object(self, **kwargs: Any) -> Any: ...


@dataclass(frozen=True)
class UploadFile:
    key: str
    body: bytes
    content_type: str


@dataclass(frozen=True)
class UploadReport:
    uploaded: tuple[str, ...]
    stale: tuple[str, ...]
    deleted: tuple[str, ...]


def normalise_prefix(prefix: str) -> str:
    """`chunks`, `/chunks` and `chunks/` all become `chunks/`. An empty prefix is refused."""
    cleaned = prefix.strip().strip("/")
    if not cleaned:
        raise ValueError(
            "an S3 prefix is required; the data source should not read the whole bucket"
        )
    return f"{cleaned}/"


def plan_upload(chunks: list[KBChunk], prefix: str) -> list[UploadFile]:
    """Two files per chunk: the text and its sidecar, side by side under `prefix`."""
    prefix = normalise_prefix(prefix)
    files: list[UploadFile] = []
    for chunk in chunks:
        files.append(
            UploadFile(
                key=f"{prefix}{chunk.name}",
                body=chunk.text.encode("utf-8"),
                content_type="text/markdown; charset=utf-8",
            )
        )
        files.append(
            UploadFile(
                key=f"{prefix}{sidecar_name(chunk.name)}",
                body=json.dumps(chunk_sidecar(chunk), indent=2).encode("utf-8"),
                content_type="application/json",
            )
        )
    keys = [file.key for file in files]
    if len(set(keys)) != len(keys):
        raise ValueError("two chunks map to the same S3 key")
    return files


def existing_keys(client: S3Client, bucket: str, prefix: str) -> set[str]:
    """Every object key under `prefix`, following S3's pagination."""
    keys: set[str] = set()
    request: dict[str, Any] = {"Bucket": bucket, "Prefix": normalise_prefix(prefix)}
    while True:
        response = client.list_objects_v2(**request)
        keys.update(item["Key"] for item in response.get("Contents", []))
        if not response.get("IsTruncated"):
            return keys
        request["ContinuationToken"] = response["NextContinuationToken"]


def upload(
    client: S3Client,
    bucket: str,
    prefix: str,
    chunks: list[KBChunk],
    *,
    delete_stale: bool = False,
) -> UploadReport:
    """Upload every chunk and sidecar, then report (and optionally delete) stale files."""
    files = plan_upload(chunks, prefix)
    for file in files:
        client.put_object(
            Bucket=bucket, Key=file.key, Body=file.body, ContentType=file.content_type
        )

    planned = {file.key for file in files}
    stale = tuple(sorted(existing_keys(client, bucket, prefix) - planned))
    deleted: tuple[str, ...] = ()
    if delete_stale:
        for key in stale:
            client.delete_object(Bucket=bucket, Key=key)
        deleted = stale
    return UploadReport(uploaded=tuple(file.key for file in files), stale=stale, deleted=deleted)
