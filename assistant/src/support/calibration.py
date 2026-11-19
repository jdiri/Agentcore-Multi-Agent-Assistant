"""Choose Support's relevance threshold from measured retrieval scores, and report the evidence.

Support gives the gap reply when the top retrieval score is below the threshold. Above it, the
model still checks whether the excerpts cover the question.

Policy (decided by Track B, 2026-11-19): the threshold is a floor. It must never refuse an
answerable question, so it sits at or below the lowest answerable score. If the answerable and
gap scores separate cleanly, it sits at the midpoint of the space between them and catches every
gap question. If they overlap, it sits at the lowest answerable score (rounded down), and the gap
questions above it are listed: those are left to the model's coverage check.
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
    gaps_above: tuple[str, ...]  # gap ids at or above the floor: left to the model's check


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


def _floor3(score: float) -> float:
    """The largest 3-decimal value not greater than `score`."""
    return math.floor(score * 1000) / 1000


def choose_threshold(rows: Sequence[ScoredQuestion]) -> Threshold:
    answerable = [r for r in rows if r.kind == ANSWERABLE]
    gaps = [r for r in rows if r.kind == GAP]
    if not answerable or not gaps:
        raise ValueError("calibration needs both answerable and gap questions")

    highest_gap = max(r.top_score for r in gaps)
    lowest_answerable = min(r.top_score for r in answerable)
    separated = lowest_answerable > highest_gap
    value = _floor3(lowest_answerable)
    if separated:
        midpoint = round((highest_gap + lowest_answerable) / 2, 3)
        if highest_gap < midpoint <= lowest_answerable:  # rounding can push it out of the space
            value = midpoint
    above = tuple(r.id for r in gaps if r.top_score >= value)
    return Threshold(value, highest_gap, lowest_answerable, separated, above)


def _decision(row: ScoredQuestion, threshold: float) -> str:
    if row.top_score < threshold:
        return "gap reply"
    return "answer" if row.kind == ANSWERABLE else "passes; model checks"


def _outcome(row: ScoredQuestion, threshold: float) -> str:
    """'yes' if the threshold decided correctly, 'model' if it was left to the model."""
    if row.top_score < threshold:
        return "yes" if row.kind == GAP else "**no**"
    return "yes" if row.kind == ANSWERABLE else "model"


def latency_summary(latencies_ms: Sequence[float]) -> dict[str, float]:
    """Median, 95th percentile (nearest rank) and max of per-call retrieval latency, in ms."""
    if not latencies_ms:
        raise ValueError("no latencies")
    ordered = sorted(latencies_ms)
    p95_rank = max(1, math.ceil(0.95 * len(ordered)))
    mid = len(ordered) // 2
    median = ordered[mid] if len(ordered) % 2 else (ordered[mid - 1] + ordered[mid]) / 2
    return {"median": median, "p95": ordered[p95_rank - 1], "max": ordered[-1]}


def render_markdown(
    rows: Sequence[ScoredQuestion],
    threshold: Threshold,
    *,
    run: str,
    latencies_ms: Sequence[float] = (),
) -> str:
    answerable = [r for r in rows if r.kind == ANSWERABLE]
    gaps = [r for r in rows if r.kind == GAP]
    refused = sum(r.top_score < threshold.value for r in answerable)
    caught = sum(r.top_score < threshold.value for r in gaps)
    left = len(gaps) - caught
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
            f" {threshold.lowest_answerable:.4f}). The threshold is a floor at the lowest"
            " answerable score, so no answerable question is refused. These gap questions score"
            " above it and are left to the model's coverage check:"
            f" {', '.join(threshold.gaps_above)}."
        )

    lines = [
        f"# Relevance threshold calibration ({run})",
        "",
        "_Synthetic data. Scores from the Bedrock managed knowledge base, `status = current`"
        " filter applied, top result per question._",
        "",
        f"**Threshold: {threshold.value:.3f}** (gap reply when the top score is below this).",
        "",
        reason,
        "",
        "| | Count |",
        "|---|---|",
        f"| Answerable questions (Q01–Q24) | {len(answerable)} |",
        f"| Gap questions (Q25 + G01–G12) | {len(gaps)} |",
        f"| Answerable refused by the threshold | {refused} / {len(answerable)} |",
        f"| Gap questions caught by the threshold | {caught} / {len(gaps)} |",
        f"| Gap questions left to the model's coverage check | {left} / {len(gaps)} |",
        f"| Answerable: top result is an expected source | {top_ok} / {len(answerable)} |",
        f"| Answerable: an expected source is in the results | {any_ok} / {len(answerable)} |",
        "",
    ]
    if latencies_ms:
        stats = latency_summary(latencies_ms)
        lines += [
            f"Retrieve latency over {len(latencies_ms)} calls (budget < 1 s):"
            f" median {stats['median']:.0f} ms, p95 {stats['p95']:.0f} ms,"
            f" max {stats['max']:.0f} ms.",
            "",
        ]
    lines += [
        "## Scores (highest first)",
        "",
        "| ID | Kind | Case | Top score | Threshold decision | Correct | Top source |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in sorted(rows, key=lambda r: r.top_score, reverse=True):
        lines.append(
            f"| {r.id} | {r.kind} | {r.case} | {r.top_score:.4f} | {_decision(r, threshold.value)}"
            f" | {_outcome(r, threshold.value)} | {r.top_source or '—'} |"
        )
    return "\n".join(lines) + "\n"
