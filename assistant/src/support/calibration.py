"""Choose Support's relevance threshold from measured retrieval scores, and report the evidence.

Support answers only when the top retrieval score is >= the threshold; below it, it gives the
gap reply. Policy (decided by Track B): prefer fewer wrong answers. So the threshold must be
above every gap question's top score. If the answerable and gap scores separate cleanly, it
sits at the midpoint of the space between them; if they overlap, it sits just above the highest
gap score and the answerable questions below it are listed (they would get the gap reply).
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass

from .retrieval import RetrievedChunk

ANSWERABLE = "answerable"
GAP = "gap"


@dataclass(frozen=True)
class ScoredQuestion:
    """One calibration question and what retrieval returned for it."""

    id: str
    question: str
    kind: str  # ANSWERABLE or GAP
    case: str  # support_qa case (standard, superseded, ...) or gap kind (off_topic, near_miss)
    top_score: float  # 0.0 when nothing was retrieved
    top_source: str  # e.g. "Account Transfer Policy v3.2, s.4", or "" when nothing was retrieved
    top_is_expected: bool | None  # answerable only: is the top hit an expected source?
    expected_in_results: bool | None  # answerable only: is any hit an expected source?


@dataclass(frozen=True)
class Threshold:
    value: float
    highest_gap: float
    lowest_answerable: float
    separated: bool
    answerable_below: tuple[str, ...]  # ids that would get the gap reply at this threshold


def matches_source(hit: RetrievedChunk, source: dict) -> bool:
    """Does a hit come from a ground-truth source (title, version and, if given, section)?"""
    if (hit.document.title, hit.document.version) != (source["title"], source["version"]):
        return False
    if "section" not in source:
        return True
    tops = {part.split(".")[0] for part in source["section"].split("-")}  # 4.1 -> 4; 2-3 -> 2, 3
    return hit.section in tops


def score_question(
    *,
    id: str,
    question: str,
    kind: str,
    case: str,
    hits: Sequence[RetrievedChunk],
    sources: Sequence[dict] = (),
) -> ScoredQuestion:
    top = hits[0] if hits else None
    expected = kind == ANSWERABLE
    return ScoredQuestion(
        id=id,
        question=question,
        kind=kind,
        case=case,
        top_score=top.score if top else 0.0,
        top_source=top.citation().as_source() if top else "",
        top_is_expected=(
            any(matches_source(top, s) for s in sources) if expected and top else None
        ),
        expected_in_results=(
            any(matches_source(h, s) for h in hits for s in sources) if expected else None
        ),
    )


def _just_above(score: float) -> float:
    """The smallest 3-decimal value strictly greater than `score`."""
    value = math.ceil(score * 1000) / 1000
    return round(value + 0.001, 3) if value <= score else value


def choose_threshold(rows: Sequence[ScoredQuestion]) -> Threshold:
    answerable = [r for r in rows if r.kind == ANSWERABLE]
    gaps = [r for r in rows if r.kind == GAP]
    if not answerable or not gaps:
        raise ValueError("calibration needs both answerable and gap questions")

    highest_gap = max(r.top_score for r in gaps)
    lowest_answerable = min(r.top_score for r in answerable)
    separated = lowest_answerable > highest_gap
    if separated:
        value = round((highest_gap + lowest_answerable) / 2, 3)
        if not highest_gap < value <= lowest_answerable:  # rounding pushed it out of the space
            value = _just_above(highest_gap)
    else:
        value = _just_above(highest_gap)
    below = tuple(r.id for r in answerable if r.top_score < value)
    return Threshold(value, highest_gap, lowest_answerable, separated, below)


def _decision(row: ScoredQuestion, threshold: float) -> str:
    return "answer" if row.top_score >= threshold else "gap reply"


def _correct(row: ScoredQuestion, threshold: float) -> bool:
    return (_decision(row, threshold) == "answer") == (row.kind == ANSWERABLE)


def render_markdown(rows: Sequence[ScoredQuestion], threshold: Threshold, *, run: str) -> str:
    answerable = [r for r in rows if r.kind == ANSWERABLE]
    gaps = [r for r in rows if r.kind == GAP]
    correct = sum(_correct(r, threshold.value) for r in rows)
    top_ok = sum(bool(r.top_is_expected) for r in answerable)
    any_ok = sum(bool(r.expected_in_results) for r in answerable)
    if threshold.separated:
        reason = (
            f"The groups separate: every gap question scored at most {threshold.highest_gap:.4f}"
            f" and every answerable question at least {threshold.lowest_answerable:.4f}."
            " The threshold is the midpoint of that space."
        )
    else:
        reason = (
            f"The groups overlap (highest gap {threshold.highest_gap:.4f}, lowest answerable"
            f" {threshold.lowest_answerable:.4f}). Policy is fewer wrong answers, so the threshold"
            " sits just above the highest gap score; these answerable questions would get the"
            f" gap reply instead: {', '.join(threshold.answerable_below)}."
        )

    lines = [
        f"# Relevance threshold calibration ({run})",
        "",
        "_Synthetic data. Scores from the Bedrock managed knowledge base, `status = current`"
        " filter applied, top result per question._",
        "",
        f"**Threshold: {threshold.value:.3f}** (answer when the top score is at least this).",
        "",
        reason,
        "",
        "| | Count |",
        "|---|---|",
        f"| Answerable questions (Q01–Q24) | {len(answerable)} |",
        f"| Gap questions (Q25 + G01–G12) | {len(gaps)} |",
        f"| Correct answer/gap decisions at this threshold | {correct} / {len(rows)} |",
        f"| Answerable: top result is an expected source | {top_ok} / {len(answerable)} |",
        f"| Answerable: an expected source is in the results | {any_ok} / {len(answerable)} |",
        "",
        "## Scores (highest first)",
        "",
        "| ID | Kind | Case | Top score | Decision | Correct | Top source |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in sorted(rows, key=lambda r: r.top_score, reverse=True):
        lines.append(
            f"| {r.id} | {r.kind} | {r.case} | {r.top_score:.4f} | {_decision(r, threshold.value)}"
            f" | {'yes' if _correct(r, threshold.value) else '**no**'} | {r.top_source or '—'} |"
        )
    return "\n".join(lines) + "\n"
