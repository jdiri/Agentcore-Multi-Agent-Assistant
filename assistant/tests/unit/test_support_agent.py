import asyncio
import logging
from pathlib import Path

import pytest

from common.contracts import ReportStatus, Specialist, SpecialistTask
from common.contracts.support import SUPPORT_GAP_REPLY
from support.agent import (
    TOOL_FAILED_DETAIL,
    DraftClaim,
    SupportAnswer,
    build_support_handler,
    cite_claims,
    render_excerpts,
)
from support.kb_metadata import split_corpus
from support.retrieval import RetrievalError, RetrievedChunk

KB_DIR = Path(__file__).resolve().parents[2] / "Project3-Corpus-Documents/p3-corpus/knowledge-base"
QUESTION = "How long does an incoming ACATS transfer take?"


@pytest.fixture(scope="module")
def chunks() -> dict[str, RetrievedChunk]:
    return {
        c.name: RetrievedChunk(c.text, c.document, c.section, f"id-{c.name}", 0.9)
        for c in split_corpus(KB_DIR)
        if not c.document.superseded
    }


def task(specialist=Specialist.SUPPORT, instruction=QUESTION) -> SpecialistTask:
    return SpecialistTask(
        task_id="t1", session_id="s1", turn_id="u1", specialist=specialist, instruction=instruction
    )


def run(retrieved, answer, *, instruction=QUESTION):
    seen = {}

    async def retriever(question):
        seen["question"] = question
        if isinstance(retrieved, Exception):
            raise retrieved
        return retrieved

    async def answerer(question, given):
        seen["answerer_chunks"] = list(given)
        if isinstance(answer, Exception):
            raise answer
        return answer

    handler = build_support_handler(retriever, answerer)
    return asyncio.run(handler(task(instruction=instruction))), seen


ACATS_QUOTE = "Incoming ACATS transfers normally complete in 3 to 6 business days"
S4 = "account-transfer-policy-v3.2__s4.md"
S7 = "account-transfer-policy-v3.2__s7.md"
WIRES = "fee-schedule-faq-2026-01__q05.md"


def claim(text, excerpt=1, quote=ACATS_QUOTE):
    return DraftClaim(claim=text, excerpt=excerpt, quote=quote)


def sources(answer, hits):
    return [c.citation.as_source() for c in cite_claims(answer, hits)]


# 1. Citations come from where the quote actually is in the retrieved text.


def test_answer_cites_the_paragraph_that_holds_the_quote(chunks):
    answer = SupportAnswer(covered=True, claims=[claim("It takes 3 to 6 business days.")])
    report, seen = run([chunks[S4]], answer)
    assert report.status is ReportStatus.COMPLETED
    assert [(f.claim, f.source) for f in report.findings] == [
        ("It takes 3 to 6 business days.", "Account Transfer Policy v3.2, s.4.1")
    ]
    assert report.tool_rounds_used == 1
    assert seen["question"] == QUESTION


def test_wrong_excerpt_number_still_cites_where_the_quote_is(chunks):
    # The live bug: the model named the Fees excerpt (s.7) for a s.4.1 fact.
    answer = SupportAnswer(covered=True, claims=[claim("3 to 6 business days.", excerpt=1)])
    assert sources(answer, [chunks[S7], chunks[S4]]) == ["Account Transfer Policy v3.2, s.4.1"]


def test_quote_in_no_retrieved_chunk_is_dropped(chunks):
    invented = claim("It takes 5 to 8 days.", quote="normally complete in 5 to 8 business days")
    answer = SupportAnswer(covered=True, claims=[invented])
    assert cite_claims(answer, [chunks[S4], chunks[S7]]) == []


def test_quote_matches_across_bold_marks_spacing_and_case(chunks):
    quote = "incoming ACATS   transfers normally complete in **3 to 6 BUSINESS days**"
    answer = SupportAnswer(covered=True, claims=[claim("x", quote=quote)])
    assert sources(answer, [chunks[S4]]) == ["Account Transfer Policy v3.2, s.4.1"]


def test_quote_from_another_subsection_cites_that_subsection(chunks):
    quote = "Non-ACATS transfers normally take 2 to 3 weeks"
    answer = SupportAnswer(covered=True, claims=[claim("x", quote=quote)])
    assert sources(answer, [chunks[S4]]) == ["Account Transfer Policy v3.2, s.4.3"]


def test_quote_of_the_context_line_is_not_evidence(chunks):
    answer = SupportAnswer(covered=True, claims=[claim("x", quote="Account Transfer Policy v3.2")])
    assert cite_claims(answer, [chunks[S4]]) == []


def test_short_quotes_are_rejected(chunks):
    answer = SupportAnswer(covered=True, claims=[claim("x", quote="business days")])
    assert cite_claims(answer, [chunks[S4]]) == []


def test_faq_claim_has_no_section(chunks):
    quote = "Each outgoing wire costs $10."
    answer = SupportAnswer(covered=True, claims=[claim("Outgoing wires cost $10.", quote=quote)])
    assert sources(answer, [chunks[WIRES]]) == ["Fee Schedule FAQ, 2026-01"]


def test_blank_claims_are_dropped(chunks):
    answer = SupportAnswer(covered=True, claims=[claim("ok"), claim("   ")])
    assert [c.claim for c in cite_claims(answer, [chunks[S4]])] == ["ok"]


def test_each_claim_cites_its_own_source(chunks):
    wires = claim("b", excerpt=2, quote="Each outgoing wire costs $10.")
    answer = SupportAnswer(covered=True, claims=[wires, claim("a")])
    report, _ = run([chunks[S4], chunks[WIRES]], answer)
    assert [f.source for f in report.findings] == [
        "Fee Schedule FAQ, 2026-01",
        "Account Transfer Policy v3.2, s.4.1",
    ]


def test_excerpts_are_numbered_and_labelled_from_metadata(chunks):
    hits = [
        chunks["account-transfer-policy-v3.2__s4.md"],
        chunks["fee-schedule-faq-2026-01__q05.md"],
    ]
    text = render_excerpts(hits)
    assert text.startswith("[Excerpt 1] Account Transfer Policy v3.2, s.4\n")
    assert "\n\n[Excerpt 2] Fee Schedule FAQ, 2026-01\n" in text
    assert "3 to 6 business days" in text


# 2. Gaps get the exact gap reply.


def test_not_covered_gives_the_gap_reply(chunks):
    hits = [chunks["account-transfer-policy-v3.2__s4.md"]]
    report, _ = run(hits, SupportAnswer(covered=False, claims=[claim("ignored")]))
    assert report.status is ReportStatus.NO_INFORMATION
    assert report.detail == SUPPORT_GAP_REPLY
    assert report.findings == ()


def test_no_results_gives_the_gap_reply_without_calling_the_model():
    report, seen = run([], SupportAnswer(covered=True, claims=[claim("x")]))
    assert report.detail == SUPPORT_GAP_REPLY
    assert "answerer_chunks" not in seen


def test_covered_but_no_usable_claims_is_a_gap(chunks):
    hits = [chunks["account-transfer-policy-v3.2__s4.md"]]
    report, _ = run(
        hits,
        SupportAnswer(
            covered=True, claims=[claim("x", 7, quote="words that are not in the policy")]
        ),
    )
    assert report.status is ReportStatus.NO_INFORMATION


# 3. Failures are reported, never filled in, and logs carry no client text.


@pytest.mark.parametrize("where", ["retrieval", "model"])
def test_failure_is_reported_as_tool_failed(chunks, where, caplog):
    hits = [chunks["account-transfer-policy-v3.2__s4.md"]]
    error = RetrievalError("bad result for How long does an incoming ACATS transfer take?")
    retrieved, answer = (error, None) if where == "retrieval" else (hits, RuntimeError("boom"))
    with caplog.at_level(logging.INFO):
        report, _ = run(retrieved, answer)
    assert report.status is ReportStatus.TOOL_FAILED
    assert report.detail == TOOL_FAILED_DETAIL
    assert report.findings == ()
    assert "ACATS" not in caplog.text and "boom" not in caplog.text


def test_logs_never_contain_the_question_or_answer(chunks, caplog):
    hits = [chunks["account-transfer-policy-v3.2__s4.md"]]
    answer = SupportAnswer(covered=True, claims=[claim("It takes 3 to 6 business days.")])
    with caplog.at_level(logging.INFO):
        run(hits, answer, instruction="My account 12345678 transfer status?")
    assert "12345678" not in caplog.text
    assert "business days" not in caplog.text
    assert "task_id=t1" in caplog.text


def test_rejects_tasks_for_other_specialists():
    handler = build_support_handler(None, None)
    with pytest.raises(ValueError, match="Support handler"):
        asyncio.run(handler(task(specialist=Specialist.RESEARCH)))
