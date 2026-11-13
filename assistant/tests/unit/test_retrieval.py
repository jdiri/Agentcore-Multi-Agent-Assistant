import logging
from pathlib import Path

import pytest

from common.contracts.support import DocumentType
from support.kb_metadata import CURRENT_ONLY_FILTER, chunk_sidecar, split_corpus
from support.retrieval import RetrievalError, RetrievedChunk, knowledge_base_id, retrieve

KB_DIR = Path(__file__).resolve().parents[2] / "Project3-Corpus-Documents/p3-corpus/knowledge-base"
QUESTION = "How long does an incoming ACATS transfer take?"


@pytest.fixture(scope="module")
def chunks():
    return {chunk.name: chunk for chunk in split_corpus(KB_DIR)}


def result(chunk, score: float, chunk_id: str = "chunk-1", **metadata_changes) -> dict:
    """A retrieval result shaped like Bedrock's, built from one of our real chunks."""
    metadata = {
        **chunk_sidecar(chunk)["metadataAttributes"],
        "x-amz-bedrock-kb-chunk-id": chunk_id,
        "x-amz-bedrock-kb-source-uri": f"s3://bucket/chunks/{chunk.name}",
        **metadata_changes,
    }
    metadata = {k: v for k, v in metadata.items() if v is not None}
    return {"content": {"text": chunk.text}, "score": score, "metadata": metadata}


class FakeClient:
    def __init__(self, results: list[dict]):
        self.results = results
        self.calls: list[dict] = []

    def retrieve(self, **kwargs):
        self.calls.append(kwargs)
        return {"retrievalResults": self.results}


def v32_s4(chunks):
    return chunks["account-transfer-policy-v3.2__s4.md"]


# 1. The request sent to Bedrock.


def test_request_always_filters_to_current(chunks):
    client = FakeClient([])
    retrieve(client, "KBID123456", QUESTION, top_k=3)
    [call] = client.calls
    assert call["knowledgeBaseId"] == "KBID123456"
    assert call["retrievalQuery"] == {"text": QUESTION}
    search = call["retrievalConfiguration"]["managedSearchConfiguration"]
    assert search == {"numberOfResults": 3, "filter": CURRENT_ONLY_FILTER}
    assert CURRENT_ONLY_FILTER == {"equals": {"key": "status", "value": "current"}}


@pytest.mark.parametrize("question", ["", "   "])
def test_blank_question_rejected(question):
    with pytest.raises(ValueError, match="blank"):
        retrieve(FakeClient([]), "KB", question)


@pytest.mark.parametrize("top_k", [0, 21])
def test_top_k_bounded(top_k):
    with pytest.raises(ValueError, match="top_k"):
        retrieve(FakeClient([]), "KB", QUESTION, top_k=top_k)


# 2. Parsing results.


def test_result_parsed_into_chunk(chunks):
    [hit] = retrieve(FakeClient([result(v32_s4(chunks), 0.71, "abc")]), "KB", QUESTION)
    assert hit.document.document_id == "POL-TRF" and hit.document.version == "3.2"
    assert hit.document.superseded is False
    assert (hit.section, hit.chunk_id, hit.score) == ("4", "abc", 0.71)
    assert hit.text.startswith("Account Transfer Policy v3.2 — 4. Timelines")


def test_results_sorted_by_score(chunks):
    results = [
        result(chunks["account-transfer-policy-v3.2__s2.md"], 0.40, "low"),
        result(v32_s4(chunks), 0.71, "high"),
    ]
    assert [hit.chunk_id for hit in retrieve(FakeClient(results), "KB", QUESTION)] == [
        "high",
        "low",
    ]


def test_no_results_is_an_empty_list():
    assert retrieve(FakeClient([]), "KB", QUESTION) == []


def test_faq_result_has_no_section(chunks):
    faq = chunks["fee-schedule-faq-2026-01__q01.md"]
    [hit] = retrieve(FakeClient([result(faq, 0.5)]), "KB", QUESTION)
    assert hit.section is None and hit.document.document_type is DocumentType.FAQ


def test_superseded_result_is_an_error(chunks):
    old = chunks["account-transfer-policy-v3.1__s4.md"]
    with pytest.raises(RetrievalError, match="passed the current-only filter"):
        retrieve(FakeClient([result(old, 0.9)]), "KB", QUESTION)


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"status": None}, "bad document metadata"),
        ({"version": "v3.2"}, "bad document metadata"),
        ({"x-amz-bedrock-kb-chunk-id": None}, "no x-amz-bedrock-kb-chunk-id or documentId"),
    ],
)
def test_bad_metadata_is_an_error(chunks, changes, message):
    with pytest.raises(RetrievalError, match=message):
        retrieve(FakeClient([result(v32_s4(chunks), 0.7, **changes)]), "KB", QUESTION)


def test_document_id_used_when_chunk_id_key_missing(chunks):
    managed = result(v32_s4(chunks), 0.7, **{"x-amz-bedrock-kb-chunk-id": None})
    managed["documentId"] = "doc-42"
    [hit] = retrieve(FakeClient([managed]), "KB", QUESTION)
    assert hit.chunk_id == "doc-42"


def test_missing_score_is_an_error(chunks):
    bad = result(v32_s4(chunks), 0.7)
    del bad["score"]
    with pytest.raises(RetrievalError, match="no score"):
        retrieve(FakeClient([bad]), "KB", QUESTION)


# 3. The question is never logged.


def test_question_not_logged(chunks, caplog):
    secret = "my account 12345678 SSN 123-45-6789"
    with caplog.at_level(logging.DEBUG, logger="support.retrieval"):
        retrieve(FakeClient([result(v32_s4(chunks), 0.71)]), "KB", secret)
    assert caplog.records, "expected a summary log line"
    assert all(
        secret not in r.getMessage() and "12345678" not in r.getMessage() for r in caplog.records
    )
    assert "1 results, top score 0.710" in caplog.text


# 4. Citations from retrieved chunks.


def hit(chunks, name: str = "account-transfer-policy-v3.2__s4.md") -> RetrievedChunk:
    [chunk] = retrieve(FakeClient([result(chunks[name], 0.71, "abc")]), "KB", QUESTION)
    return chunk


def test_citation_uses_chunk_section(chunks):
    citation = hit(chunks).citation()
    assert citation.as_source() == "Account Transfer Policy v3.2, s.4"
    assert (citation.chunk_id, citation.score) == ("abc", 0.71)


def test_citation_narrowed_to_subsection_in_text(chunks):
    assert hit(chunks).citation("4.1").as_source() == "Account Transfer Policy v3.2, s.4.1"


@pytest.mark.parametrize(
    ("subsection", "message"),
    [("4.9", "not in the retrieved text"), ("5.1", "not inside section 4"), ("41", "not inside")],
)
def test_citation_narrowing_refused(chunks, subsection, message):
    with pytest.raises(ValueError, match=message):
        hit(chunks).citation(subsection)


def test_faq_citation_cannot_be_narrowed(chunks):
    faq = hit(chunks, "fee-schedule-faq-2026-01__q01.md")
    assert faq.citation().as_source() == "Fee Schedule FAQ, 2026-01"
    with pytest.raises(ValueError, match="not inside section None"):
        faq.citation("1.1")


# 5. Configuration.


def test_knowledge_base_id_from_env(monkeypatch):
    monkeypatch.setenv("P3_KB_ID", " KBID123456 ")
    assert knowledge_base_id() == "KBID123456"


def test_missing_knowledge_base_id(monkeypatch):
    monkeypatch.delenv("P3_KB_ID", raising=False)
    with pytest.raises(RuntimeError, match="P3_KB_ID is not set"):
        knowledge_base_id()
