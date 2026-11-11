import json
from pathlib import Path

import pytest

from common.contracts.support import DocumentType, KBDocument
from support.kb_metadata import (
    KBHeaderError,
    load_corpus,
    mark_superseded,
    parse_header,
    sidecar,
    sidecar_name,
)

KB_DIR = Path(__file__).resolve().parents[2] / "Project3-Corpus-Documents/p3-corpus/knowledge-base"

HEADER = """# Account Transfer Policy

Document ID: POL-TRF
Version: 3.2
Effective: 2026-03-01
Supersedes: 3.1
Owner: Client Services Operations

## 1. Purpose

Body text: with a colon, which is fine after the header.
"""


# 1. The real corpus.


@pytest.fixture(scope="module")
def corpus() -> dict[str, KBDocument]:
    return load_corpus(KB_DIR)


def test_corpus_loads_18_documents(corpus):
    assert len(corpus) == 18


def test_only_transfer_policy_v31_is_superseded(corpus):
    superseded = [name for name, document in corpus.items() if document.superseded]
    assert superseded == ["account-transfer-policy-v3.1.md"]


def test_transfer_policy_v32_is_current(corpus):
    current = corpus["account-transfer-policy-v3.2.md"]
    assert (current.document_id, current.version, current.supersedes) == ("POL-TRF", "3.2", "3.1")
    assert current.superseded is False


def test_corpus_header_values(corpus):
    notice = corpus["trading-hours-and-market-holidays-notice-2026.md"]
    assert notice.title == "Trading Hours & Market Holidays Notice"
    assert notice.document_type is DocumentType.NOTICE
    assert (notice.version, notice.supersedes, notice.owner) == ("2026", "2025", "Fund Operations")


def test_corpus_keys_are_sorted_file_names(corpus):
    assert list(corpus) == sorted(path.name for path in KB_DIR.glob("*.md"))


# 2. Parsing one header.


def test_parse_header():
    document = parse_header(HEADER, "x.md")
    assert document == KBDocument(
        document_id="POL-TRF",
        title="Account Transfer Policy",
        version="3.2",
        supersedes="3.1",
        owner="Client Services Operations",
    )


def test_faq_body_right_after_header():
    faq = HEADER.split("## ")[0] + "**Is there a fee?**\nYes: $25 a year.\n"
    assert parse_header(faq, "x.md").version == "3.2"


def test_supersedes_is_optional():
    assert parse_header(HEADER.replace("Supersedes: 3.1\n", ""), "x.md").supersedes is None


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (("# Account Transfer Policy\n", ""), "no '# ' title"),
        (("Owner:", "# Second Title\nOwner:"), "more than one title"),
        (("Version: 3.2\n", "Version: 3.2\nVersion: 3.3\n"), "Version appears twice"),
        (("Owner:", "Status: current\nOwner:"), "unexpected header line 'Status: current'"),
        (("Owner:", "just some words\nOwner:"), "unexpected header line"),
        (("Version: 3.2\n", ""), "version"),  # missing required field
        (("POL-TRF", "POL-TRANSFER"), "document_id"),  # fails the KBDocument pattern
    ],
)
def test_bad_header_stops_with_file_name(change, message):
    with pytest.raises(KBHeaderError, match="^bad.md: ") as raised:
        parse_header(HEADER.replace(*change), "bad.md")
    assert message in str(raised.value)


# 3. Marking superseded versions.


def doc(version: str, supersedes: str | None, document_id: str = "POL-TRF") -> KBDocument:
    return KBDocument(
        document_id=document_id,
        title="Some Policy",
        version=version,
        supersedes=supersedes,
        owner="Owner",
    )


def test_chain_marks_every_replaced_version():
    marked = mark_superseded(
        {"a": doc("3.0", None), "b": doc("3.1", "3.0"), "c": doc("3.2", "3.1")}
    )
    assert {name: d.superseded for name, d in marked.items()} == {"a": True, "b": True, "c": False}


def test_supersedes_only_applies_within_the_same_document_id():
    marked = mark_superseded({"a": doc("3.1", None), "b": doc("3.2", "3.1", document_id="POL-WDR")})
    assert not any(d.superseded for d in marked.values())


def test_previous_version_not_in_corpus_is_fine():
    assert mark_superseded({"a": doc("3.2", "3.1")})["a"].superseded is False


def test_duplicate_id_and_version_rejected():
    with pytest.raises(KBHeaderError, match="a and b are both POL-TRF v3.2"):
        mark_superseded({"a": doc("3.2", "3.1"), "b": doc("3.2", "3.1")})


def test_empty_directory_rejected(tmp_path):
    with pytest.raises(KBHeaderError, match="no .md files"):
        load_corpus(tmp_path)


def test_bad_file_in_directory_stops_the_load(tmp_path):
    (tmp_path / "good.md").write_text(HEADER, encoding="utf-8")
    (tmp_path / "bad.md").write_text("no header here\n", encoding="utf-8")
    with pytest.raises(KBHeaderError, match="^bad.md: "):
        load_corpus(tmp_path)


# 4. Sidecar files for the S3 upload.


def test_sidecar_name():
    assert (
        sidecar_name("fee-schedule-faq-2026-01.md") == "fee-schedule-faq-2026-01.md.metadata.json"
    )


def test_sidecar_for_superseded_policy(corpus):
    assert sidecar(corpus["account-transfer-policy-v3.1.md"]) == {
        "metadataAttributes": {
            "document_id": "POL-TRF",
            "title": "Account Transfer Policy",
            "version": "3.1",
            "supersedes": "3.0",
            "owner": "Client Services Operations",
            "superseded": True,
            "document_type": "policy",
        }
    }


def test_sidecar_leaves_out_missing_supersedes():
    assert "supersedes" not in sidecar(doc("3.2", None))["metadataAttributes"]


def test_every_corpus_sidecar_uses_bedrock_value_types(corpus):
    for document in corpus.values():
        for key, value in sidecar(document)["metadataAttributes"].items():
            expected = bool if key == "superseded" else str
            assert type(value) is expected, (document.title, key)


def test_sidecar_is_json_and_loads_back(corpus):
    for document in corpus.values():
        body = json.loads(json.dumps(sidecar(document)))
        assert KBDocument(**body["metadataAttributes"]) == document
