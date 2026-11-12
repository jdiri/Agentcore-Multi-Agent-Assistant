import asyncio
from collections import Counter
from pathlib import Path

import pytest

from common.contracts import RefusalReason, RoutingDecision, Specialist
from coordinator.routing_eval import (
    RoutingCase,
    load_cases,
    render_report,
    run_cases,
    score_case,
)

ROUTING_JSONL = (
    Path(__file__).resolve().parents[2]
    / "Project3-Corpus-Documents/p3-corpus/ground-truth/routing.jsonl"
)

S, R, A = Specialist.SUPPORT, Specialist.RESEARCH, Specialist.ACTION


def route(*specialists):
    return RoutingDecision(
        delegations=[{"specialist": s, "task": f"{s} task"} for s in specialists]
    )


def refuse(reason):
    return RoutingDecision(refusal=reason)


TWO_PART = RoutingCase("T1", "two parts", expected=(S, R), also_acceptable=((R, S),))
ADVICE = RoutingCase("T2", "advice", expected=(), refusal=RefusalReason.INVESTMENT_ADVICE)
CROSS_USER = RoutingCase("T3", "other user", expected=(R,), also_acceptable=((),))


def test_real_ground_truth_loads_all_cases():
    cases = load_cases(ROUTING_JSONL)
    assert [case.id for case in cases] == [f"R{n:02d}" for n in range(1, 47)]
    counts = Counter(case.category for case in cases)
    assert sum(counts.values()) == 46
    assert all(case.refusal for case in cases if case.category == "refusal")


def test_unknown_specialist_is_rejected(tmp_path):
    bad = tmp_path / "bad.jsonl"
    bad.write_text('{"id": "X", "message": "m", "expected": ["billing"]}\n', encoding="utf-8")
    with pytest.raises(ValueError):
        load_cases(bad)


@pytest.mark.parametrize(
    ("case", "decision", "passed"),
    [
        (TWO_PART, route(S, R), True),  # exact match
        (TWO_PART, route(R, S), True),  # also_acceptable order
        (TWO_PART, route(S), False),  # missing a part
        (TWO_PART, route(S, R, A), False),  # extra part
        (TWO_PART, refuse(RefusalReason.OFF_TOPIC), False),  # refused a valid request
        (ADVICE, refuse(RefusalReason.INVESTMENT_ADVICE), True),
        (ADVICE, refuse(RefusalReason.OFF_TOPIC), False),  # wrong reason
        (ADVICE, route(S, A), False),  # delegated instead of refusing
        (CROSS_USER, route(R), True),
        (CROSS_USER, refuse(RefusalReason.CROSS_CLIENT), True),  # any refusal is acceptable
        (CROSS_USER, route(S), False),
    ],
)
def test_score_case(case, decision, passed):
    assert score_case(case, decision).passed is passed


def test_wrong_order_fails_without_an_alternative():
    case = RoutingCase("T4", "m", expected=(R, A))
    assert not score_case(case, route(A, R)).passed


def test_missing_decision_fails_and_keeps_the_error_type():
    result = score_case(ADVICE, None, "ThrottlingException")
    assert not result.passed
    assert result.error == "ThrottlingException"


def test_run_cases_scores_each_case_and_contains_errors():
    decisions = {TWO_PART.message: route(S, R), ADVICE.message: route(S)}

    async def fake_router(message):
        if message == CROSS_USER.message:
            raise TimeoutError("contains client text")
        return decisions[message]

    results = asyncio.run(run_cases(fake_router, [TWO_PART, ADVICE, CROSS_USER], concurrency=2))
    assert [(r.case_id, r.passed) for r in results] == [("T1", True), ("T2", False), ("T3", False)]
    assert results[2].error == "TimeoutError"


def test_report_shows_scores_and_failures():
    cases = [TWO_PART, ADVICE]
    run_1 = [score_case(TWO_PART, route(S, R)), score_case(ADVICE, route(S))]
    run_2 = [score_case(TWO_PART, route(S, R)), score_case(ADVICE, None, "TimeoutError")]
    report = render_report("test-model", [run_1, run_2], cases)

    assert "`test-model`" in report
    assert "| 1 | **1/2** |" in report
    assert (
        "| T2 | refusal | refusal: investment_advice | 0/2 | error: TimeoutError; support |"
        in report
    )
    assert "- **T2**" in report
    assert "- **T1**" not in report
