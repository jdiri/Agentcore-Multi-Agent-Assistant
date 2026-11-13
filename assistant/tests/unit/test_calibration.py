from pathlib import Path

import pytest

from support.calibration import (
    ANSWERABLE,
    GAP,
    ScoredQuestion,
    choose_threshold,
    matches_source,
    render_markdown,
    score_question,
)
from support.kb_metadata import split_corpus
from support.retrieval import RetrievedChunk

KB_DIR = Path(__file__).resolve().parents[2] / "Project3-Corpus-Documents/p3-corpus/knowledge-base"


def row(id: str, kind: str, score: float) -> ScoredQuestion:
    expected = True if kind == ANSWERABLE else None
    return ScoredQuestion(id, f"question {id}", kind, "standard", score, "Src", expected, expected)


@pytest.fixture(scope="module")
def hits() -> dict[str, RetrievedChunk]:
    out = {}
    for chunk in split_corpus(KB_DIR):
        if chunk.document.superseded:
            continue
        out[chunk.name] = RetrievedChunk(chunk.text, chunk.document, chunk.section, "id", 0.5)
    return out


# 1. Choosing the threshold.


def test_separated_scores_use_the_midpoint():
    threshold = choose_threshold(
        [row("A1", ANSWERABLE, 0.80), row("A2", ANSWERABLE, 0.60), row("G1", GAP, 0.40)]
    )
    assert threshold.separated is True
    assert threshold.value == 0.5
    assert threshold.answerable_below == ()


def test_overlap_puts_threshold_just_above_highest_gap():
    threshold = choose_threshold(
        [
            row("A1", ANSWERABLE, 0.80),
            row("A2", ANSWERABLE, 0.45),
            row("G1", GAP, 0.50),
            row("G2", GAP, 0.20),
        ]
    )
    assert threshold.separated is False
    assert threshold.value == 0.501
    assert threshold.answerable_below == ("A2",)


def test_threshold_is_always_strictly_above_every_gap_score():
    for gap in [0.5, 0.5004, 0.4999, 0.123456]:
        threshold = choose_threshold([row("A", ANSWERABLE, gap), row("G", GAP, gap)])
        assert threshold.value > gap


def test_tiny_separation_still_keeps_gaps_below():
    threshold = choose_threshold([row("A", ANSWERABLE, 0.5004), row("G", GAP, 0.5001)])
    assert threshold.value > 0.5001


@pytest.mark.parametrize("kind", [ANSWERABLE, GAP])
def test_both_groups_required(kind):
    with pytest.raises(ValueError, match="both answerable and gap"):
        choose_threshold([row("X", kind, 0.5)])


# 2. Scoring one question against retrieval hits.


def test_matches_source_with_subsection(hits):
    hit = hits["account-transfer-policy-v3.2__s4.md"]
    assert matches_source(
        hit, {"title": "Account Transfer Policy", "version": "3.2", "section": "4.1"}
    )
    assert not matches_source(
        hit, {"title": "Account Transfer Policy", "version": "3.2", "section": "5.1"}
    )
    assert not matches_source(hit, {"title": "Account Transfer Policy", "version": "3.1"})


def test_matches_section_range(hits):
    source = {"title": "Frequent Trading Policy", "version": "1.4", "section": "2-3"}
    assert matches_source(hits["frequent-trading-policy-v1.4__s3.md"], source)
    assert not matches_source(hits["frequent-trading-policy-v1.4__s4.md"], source)


def test_matches_faq_without_section(hits):
    source = {"title": "Fee Schedule FAQ", "version": "2026-01"}
    assert matches_source(hits["fee-schedule-faq-2026-01__q05.md"], source)


def test_score_answerable_question(hits):
    scored = score_question(
        id="Q01",
        question="q",
        kind=ANSWERABLE,
        case="superseded",
        hits=[
            hits["account-transfer-policy-v3.2__s2.md"],
            hits["account-transfer-policy-v3.2__s4.md"],
        ],
        sources=[{"title": "Account Transfer Policy", "version": "3.2", "section": "4.1"}],
    )
    assert scored.top_score == 0.5
    assert scored.top_source == "Account Transfer Policy v3.2, s.2"
    assert scored.top_is_expected is False
    assert scored.expected_in_results is True


def test_score_gap_question_with_no_results():
    scored = score_question(id="G01", question="q", kind=GAP, case="off_topic", hits=[])
    assert (scored.top_score, scored.top_source) == (0.0, "")
    assert scored.top_is_expected is None and scored.expected_in_results is None


# 3. The evidence files.


ROWS = [row("A1", ANSWERABLE, 0.8), row("A2", ANSWERABLE, 0.45), row("G1", GAP, 0.5)]


def test_markdown_states_threshold_and_reason():
    text = render_markdown(ROWS, choose_threshold(ROWS), run="2026-11-12")
    assert "**Threshold: 0.501**" in text
    assert "The groups overlap" in text and "A2" in text
    assert "_Synthetic data." in text
    assert "| Correct answer/gap decisions at this threshold | 2 / 3 |" in text


def test_markdown_rows_sorted_by_score_with_decisions():
    text = render_markdown(ROWS, choose_threshold(ROWS), run="2026-11-12")
    table = [line for line in text.splitlines() if line.startswith(("| A1 ", "| A2 ", "| G1 "))]
    assert [line.split(" | ")[0] for line in table] == ["| A1", "| G1", "| A2"]
    assert "| answer | yes |" in table[0]
    assert "| gap reply | yes |" in table[1]
    assert "| gap reply | **no** |" in table[2]
