import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from common.contracts.routing import (
    Delegation,
    ReportStatus,
    RoutingDecision,
    Specialist,
    SpecialistTask,
)
from common.contracts.support import (
    SUPPORT_GAP_REPLY,
    CitedClaim,
    DocumentType,
    KBCitation,
    KBDocument,
    gap_report,
)
from coordinator.graph import _render_reply

SUPPORT_QA = (
    Path(__file__).resolve().parents[2]
    / "Project3-Corpus-Documents/p3-corpus/ground-truth/support_qa.jsonl"
)

# Header values from the 18 files in p3-corpus/knowledge-base, typed in so these tests check
# the model only. Reading the real files is the loader's job and gets its own tests.
CSO = "Client Services Operations"
CORPUS_HEADERS = [
    ("POL-SEC", "Account Access & Security Policy", "4.0", "3.4", "Information Security"),
    ("POL-CLS", "Account Closure Policy", "1.2", "1.1", CSO),
    ("POL-TRF", "Account Transfer Policy", "3.1", "3.0", CSO),
    ("POL-TRF", "Account Transfer Policy", "3.2", "3.1", CSO),
    ("GDE-ACT", "Account Types Guide", "1.5", "1.4", CSO),
    ("FAQ-PRF", "Address & Profile Changes FAQ", "2025-04", "2023-10", CSO),
    ("OVR-ADV", "Advisor Services Overview", "1.2", "1.1", "Advice Services"),
    ("FAQ-AIP", "Automatic Investment Plan FAQ", "2025-06", "2024-01", CSO),
    ("POL-DEP", "Contributions & Deposits Policy", "2.1", "2.0", CSO),
    ("FAQ-DIV", "Dividends & Distributions FAQ", "2025-12", "2024-12", "Fund Operations"),
    ("FAQ-FEE", "Fee Schedule FAQ", "2026-01", "2025-01", CSO),
    ("POL-FTP", "Frequent Trading Policy", "1.4", "1.3", "Fund Operations"),
    ("FAQ-FND", "Fund Minimums & Investment Options FAQ", "2026-02", "2025-02", "Fund Operations"),
    ("NTC-PRV", "Privacy & Information Sharing Notice", "3.0", "2.2", "Privacy Office"),
    ("FAQ-STM", "Statements & Documents FAQ", "2025-09", "2024-06", "Client Communications"),
    ("POL-TKT", "Support Ticket Handling Policy", "2.0", "1.6", CSO),
    ("NTC-HOL", "Trading Hours & Market Holidays Notice", "2026", "2025", "Fund Operations"),
    ("POL-WDR", "Withdrawals & Redemptions Policy", "2.3", "2.2", CSO),
]

EXPECTED_TYPE = {
    "POL": DocumentType.POLICY,
    "FAQ": DocumentType.FAQ,
    "GDE": DocumentType.GUIDE,
    "OVR": DocumentType.OVERVIEW,
    "NTC": DocumentType.NOTICE,
}

VALID = {
    "document_id": "POL-TRF",
    "title": "Account Transfer Policy",
    "version": "3.2",
    "supersedes": "3.1",
    "owner": "Client Services Operations",
}


def doc(**overrides) -> KBDocument:
    return KBDocument(**{**VALID, **overrides})


# 1. All 18 real headers parse with the right type.


def test_corpus_has_18_documents():
    assert len(CORPUS_HEADERS) == 18


@pytest.mark.parametrize(
    ("document_id", "title", "version", "supersedes", "owner"),
    CORPUS_HEADERS,
    ids=[f"{row[0]}-{row[2]}" for row in CORPUS_HEADERS],
)
def test_corpus_header_parses(document_id, title, version, supersedes, owner):
    document = KBDocument(
        document_id=document_id,
        title=title,
        version=version,
        supersedes=supersedes,
        owner=owner,
    )
    assert document.document_type is EXPECTED_TYPE[document_id[:3]]
    assert document.superseded is False  # only the loader sets this


def test_corpus_type_counts():
    types = [
        KBDocument(document_id=i, title=t, version=v, supersedes=s, owner=o).document_type
        for i, t, v, s, o in CORPUS_HEADERS
    ]
    assert types.count(DocumentType.POLICY) == 8  # both transfer policy versions count
    assert types.count(DocumentType.FAQ) == 6
    assert types.count(DocumentType.NOTICE) == 2
    assert types.count(DocumentType.GUIDE) == 1
    assert types.count(DocumentType.OVERVIEW) == 1


def test_document_id_is_shared_across_versions():
    # Both transfer policies are POL-TRF, so a document is identified by id plus version.
    transfer = [(i, v) for i, _, v, _, _ in CORPUS_HEADERS if i == "POL-TRF"]
    assert transfer == [("POL-TRF", "3.1"), ("POL-TRF", "3.2")]
    assert len({(i, v) for i, _, v, _, _ in CORPUS_HEADERS}) == 18


# 2. Bad input is rejected.


@pytest.mark.parametrize(
    "document_id",
    ["XYZ-ABC", "pol-trf", "POL-TR", "POL-TRFX", "POLTRF", "POL_TRF", ""],
)
def test_bad_document_id_rejected(document_id):
    with pytest.raises(ValidationError):
        doc(document_id=document_id)


@pytest.mark.parametrize("version", ["v3.2", "3", "3.2.1", "2026-1", "26-01", "2026-01-15", ""])
def test_bad_version_rejected(version):
    with pytest.raises(ValidationError):
        doc(version=version)


@pytest.mark.parametrize("version", ["3.2", "2026-01", "2026"])
def test_all_three_version_formats_accepted(version):
    assert doc(version=version).version == version


def test_bad_supersedes_rejected():
    with pytest.raises(ValidationError):
        doc(supersedes="v3.1")


def test_supersedes_is_optional():
    assert doc(supersedes=None).supersedes is None


@pytest.mark.parametrize("field", ["title", "owner"])
@pytest.mark.parametrize("value", ["", "   "])
def test_blank_text_rejected(field, value):
    with pytest.raises(ValidationError):
        doc(**{field: value})


@pytest.mark.parametrize("field", ["document_id", "title", "version", "owner"])
def test_required_fields(field):
    data = {k: v for k, v in VALID.items() if k != field}
    with pytest.raises(ValidationError):
        KBDocument(**data)


def test_unknown_field_rejected():
    with pytest.raises(ValidationError):
        doc(effective="2026-04-01")


# 3. document_type behaviour.


def test_document_type_filled_from_prefix():
    assert doc().document_type is DocumentType.POLICY
    assert doc(document_id="FAQ-FEE", version="2026-01").document_type is DocumentType.FAQ


def test_matching_document_type_accepted():
    assert doc(document_type="policy").document_type is DocumentType.POLICY


def test_mismatched_document_type_rejected():
    with pytest.raises(ValidationError, match="does not match POL-TRF"):
        doc(document_type="faq")


def test_unknown_document_type_rejected():
    with pytest.raises(ValidationError):
        doc(document_type="memo")


def test_round_trip_through_dict():
    original = doc(superseded=True)
    assert KBDocument.model_validate(original.model_dump()) == original


def test_round_trip_through_json():
    original = doc(document_id="NTC-HOL", version="2026", supersedes="2025")
    assert KBDocument.model_validate_json(original.model_dump_json()) == original


# 4. Documents can't be changed after they are created.


def test_document_is_frozen():
    document = doc()
    with pytest.raises(ValidationError):
        document.superseded = True


def test_loader_marks_superseded_with_a_copy():
    current = doc(version="3.1", supersedes="3.0")
    marked = current.model_copy(update={"superseded": True})
    assert marked.superseded is True
    assert current.superseded is False


# 5. KBCitation: built from a document plus retrieval metadata.


def corpus_document(title: str, version: str) -> KBDocument:
    for i, t, v, sup, o in CORPUS_HEADERS:
        if t == title and v == version:
            return KBDocument(document_id=i, title=t, version=v, supersedes=sup, owner=o)
    raise LookupError(f"{title} v{version} is not in the corpus")


def cite(title: str, version: str, section: str | None = None, **retrieval) -> KBCitation:
    retrieval = {"chunk_id": "chunk-1", "score": 0.8, **retrieval}
    return KBCitation.from_document(corpus_document(title, version), section=section, **retrieval)


def load_sources() -> list[tuple[str, dict]]:
    rows = [json.loads(line) for line in SUPPORT_QA.read_text(encoding="utf-8").splitlines()]
    return [(row["id"], source) for row in rows for source in row["sources"]]


GROUND_TRUTH_SOURCES = load_sources()


def test_ground_truth_has_sources_for_24_questions():
    assert len({qid for qid, _ in GROUND_TRUTH_SOURCES}) == 24  # Q25 is the gap, with none


@pytest.mark.parametrize(
    ("qid", "source"),
    GROUND_TRUTH_SOURCES,
    ids=[f"{qid}-{s['title']}" for qid, s in GROUND_TRUTH_SOURCES],
)
def test_every_ground_truth_source_is_citable(qid, source):
    citation = cite(source["title"], source["version"], source.get("section"))
    rendered = citation.as_source()
    assert rendered.startswith(source["title"])
    assert source["version"] in rendered
    if "section" in source:
        assert rendered.endswith(f", s.{source['section']}")


@pytest.mark.parametrize(
    ("title", "version", "section", "expected"),
    [
        ("Account Transfer Policy", "3.2", "4.1", "Account Transfer Policy v3.2, s.4.1"),
        (
            "Withdrawals & Redemptions Policy",
            "2.3",
            "4",
            "Withdrawals & Redemptions Policy v2.3, s.4",
        ),
        ("Frequent Trading Policy", "1.4", "2-3", "Frequent Trading Policy v1.4, s.2-3"),
        ("Fee Schedule FAQ", "2026-01", None, "Fee Schedule FAQ, 2026-01"),
        (
            "Trading Hours & Market Holidays Notice",
            "2026",
            None,
            "Trading Hours & Market Holidays Notice, 2026",
        ),
        (
            "Trading Hours & Market Holidays Notice",
            "2026",
            "3",
            "Trading Hours & Market Holidays Notice, 2026, s.3",
        ),
        ("Account Types Guide", "1.5", "2.3", "Account Types Guide v1.5, s.2.3"),
        (
            "Privacy & Information Sharing Notice",
            "3.0",
            "2.2",
            "Privacy & Information Sharing Notice v3.0, s.2.2",
        ),
    ],
)
def test_as_source_matches_brief_format(title, version, section, expected):
    assert cite(title, version, section).as_source() == expected


def test_from_document_copies_document_fields():
    citation = cite("Account Transfer Policy", "3.2", "4.1", chunk_id="abc-123", score=0.61)
    assert citation.document_id == "POL-TRF"
    assert citation.document_title == "Account Transfer Policy"
    assert citation.version == "3.2"
    assert citation.document_type is DocumentType.POLICY
    assert (citation.chunk_id, citation.score) == ("abc-123", 0.61)


def test_superseded_document_refused():
    old = corpus_document("Account Transfer Policy", "3.1").model_copy(update={"superseded": True})
    with pytest.raises(ValueError, match="v3.1 is superseded"):
        KBCitation.from_document(old, chunk_id="chunk-1", score=0.9, section="4.1")


def test_unmarked_old_version_is_citable():
    # The contract trusts the loader's flag; marking v3.1 superseded is the loader's job.
    assert cite("Account Transfer Policy", "3.1", "4.1").version == "3.1"


# 6. Section rules, from the ground truth.


def test_policy_needs_a_section():
    with pytest.raises(ValidationError, match="policy citation needs a section"):
        cite("Account Transfer Policy", "3.2")


def test_faq_has_no_section():
    with pytest.raises(ValidationError, match="FAQ citation has no section"):
        cite("Fee Schedule FAQ", "2026-01", "2")


@pytest.mark.parametrize(
    ("title", "version"),
    [
        ("Account Types Guide", "1.5"),
        ("Trading Hours & Market Holidays Notice", "2026"),
        ("Advisor Services Overview", "1.2"),
    ],
)
@pytest.mark.parametrize("section", [None, "3"])
def test_section_optional_for_other_types(title, version, section):
    assert cite(title, version, section).section == section


@pytest.mark.parametrize("section", ["s.4", "4.", ".4", "4-", "four", "4 - 5", ""])
def test_bad_section_rejected(section):
    with pytest.raises(ValidationError):
        cite("Account Transfer Policy", "3.2", section)


# 7. Retrieval metadata is required and checked.


def test_negative_score_rejected():
    with pytest.raises(ValidationError):
        cite("Account Transfer Policy", "3.2", "4.1", score=-0.1)


def test_zero_score_accepted():
    assert cite("Account Transfer Policy", "3.2", "4.1", score=0).score == 0


@pytest.mark.parametrize("chunk_id", ["", "   "])
def test_blank_chunk_id_rejected(chunk_id):
    with pytest.raises(ValidationError):
        cite("Account Transfer Policy", "3.2", "4.1", chunk_id=chunk_id)


@pytest.mark.parametrize("field", ["chunk_id", "score"])
def test_retrieval_fields_required(field):
    data = cite("Account Transfer Policy", "3.2", "4.1").model_dump(exclude={field})
    with pytest.raises(ValidationError):
        KBCitation(**data)


def test_citation_round_trip_through_json():
    original = cite("Trading Hours & Market Holidays Notice", "2026", "3")
    assert KBCitation.model_validate_json(original.model_dump_json()) == original


# 8. CitedClaim becomes a Coordinator Finding.


def test_cited_claim_as_finding():
    claim = CitedClaim(
        claim="Incoming ACATS transfers normally take 3 to 6 business days.",
        citation=cite("Account Transfer Policy", "3.2", "4.1"),
    )
    finding = claim.as_finding()
    assert finding.claim == claim.claim
    assert finding.source == "Account Transfer Policy v3.2, s.4.1"


# 9. The gap report: NO_INFORMATION with the brief's exact reply.


def task(specialist: Specialist = Specialist.SUPPORT) -> SpecialistTask:
    return SpecialistTask(
        task_id="task-1",
        session_id="session-1",
        turn_id="turn-1",
        specialist=specialist,
        instruction="Answer from the knowledge base.",
    )


def test_gap_reply_is_the_brief_wording():
    assert SUPPORT_GAP_REPLY == (
        "I don't have that information in my documents. Would you like me to open a ticket?"
    )


def test_gap_report_fields():
    report = gap_report(task(), tool_rounds_used=1)
    assert report.task_id == "task-1"
    assert report.specialist is Specialist.SUPPORT
    assert report.status is ReportStatus.NO_INFORMATION
    assert report.detail == SUPPORT_GAP_REPLY
    assert report.findings == ()
    assert report.tool_rounds_used == 1


def test_gap_report_defaults_to_zero_rounds():
    assert gap_report(task()).tool_rounds_used == 0


def test_gap_report_rounds_are_bounded():
    with pytest.raises(ValidationError):
        gap_report(task(), tool_rounds_used=4)


@pytest.mark.parametrize("specialist", [s for s in Specialist if s is not Specialist.SUPPORT])
def test_gap_report_refuses_other_specialists(specialist):
    with pytest.raises(ValueError, match="for Support tasks"):
        gap_report(task(specialist))


def test_coordinator_shows_gap_reply_exactly_without_sources():
    # Uses the Coordinator's own renderer (Track A) to prove the reply reaches the client as is.
    decision = RoutingDecision(
        delegations=(Delegation(specialist=Specialist.SUPPORT, task="Answer it."),)
    )
    assert _render_reply(decision, [gap_report(task())]) == SUPPORT_GAP_REPLY
