import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from assistant.src.common.contracts import (
    MAX_TOOL_ROUNDS,
    Finding,
    ReportStatus,
    RoutingDecision,
    Specialist,
    SpecialistReport,
    SpecialistTask,
)

ROUTING_PATH = (
    Path(__file__).resolve().parents[2]
    / "Project3-Corpus-Documents/p3-corpus/ground-truth/routing.jsonl"
)
ROWS = [json.loads(line) for line in ROUTING_PATH.read_text(encoding="utf-8").splitlines() if line]
FINDING = Finding(claim="LFTS1 returned 3%", source="get_fund_returns:LFTS1")


def plan(*specialists: str, **fields) -> RoutingDecision:
    return RoutingDecision(
        delegations=[{"specialist": name, "task": "do the work", **fields} for name in specialists]
    )


def ground_truth_routes():
    for row in ROWS:
        yield pytest.param(row["expected"], row.get("refusal"), id=f"{row['id']}-expected")
        for index, route in enumerate(row.get("also_acceptable", [])):
            yield pytest.param(route, None, id=f"{row['id']}-alt{index}")


def test_ground_truth_file_is_complete():
    assert len(ROWS) == 46


@pytest.mark.parametrize(("route", "refusal"), list(ground_truth_routes()))
def test_every_ground_truth_route_is_representable(route, refusal):
    if route:
        decision = plan(*route)
        assert [d.specialist.value for d in decision.delegations] == route
    else:
        # R46 accepts a refusal but has no label for it.
        decision = RoutingDecision(refusal=refusal or "cross_client")
        assert decision.delegations == ()


def test_invented_destination_is_rejected():
    with pytest.raises(ValidationError):
        plan("billing")


def test_schema_constrains_destination_for_structured_output():
    schema = RoutingDecision.model_json_schema()
    assert schema["$defs"]["Specialist"]["enum"] == ["support", "research", "action"]


def test_refusal_and_delegations_together_are_rejected():
    with pytest.raises(ValidationError):
        RoutingDecision(
            delegations=[{"specialist": "support", "task": "answer"}],
            refusal="off_topic",
        )


def test_empty_decision_is_rejected():
    with pytest.raises(ValidationError):
        RoutingDecision()


def test_exactly_four_handoffs_with_justified_repeat_pass():
    decision = RoutingDecision(
        delegations=[
            {"specialist": "research", "task": "look up holdings"},
            {"specialist": "support", "task": "find the transfer policy"},
            {"specialist": "action", "task": "open a ticket"},
            {
                "specialist": "research",
                "task": "look up the second fund",
                "repeat_justification": "The ticket outcome named a fund the first lookup missed.",
            },
        ]
    )
    assert len(decision.delegations) == 4


def test_five_handoffs_are_rejected():
    with pytest.raises(ValidationError):
        plan("support", "research", "action", "support", "research", repeat_justification="why")


def test_repeat_without_justification_is_rejected():
    with pytest.raises(ValidationError):
        plan("research", "research")


def test_blank_justification_is_rejected():
    with pytest.raises(ValidationError):
        plan("research", "research", repeat_justification="   ")


def test_task_cannot_carry_client_identity():
    with pytest.raises(ValidationError):
        SpecialistTask(
            task_id="t-1",
            session_id="s-1",
            turn_id="turn-1",
            specialist="research",
            instruction="list holdings",
            user_id="u-001",
        )


def test_completed_report_needs_a_finding():
    with pytest.raises(ValidationError):
        SpecialistReport(task_id="t-1", specialist="research", status="completed")


@pytest.mark.parametrize("status", [s for s in ReportStatus if s is not ReportStatus.COMPLETED])
def test_non_completed_report_needs_detail(status):
    with pytest.raises(ValidationError):
        SpecialistReport(
            task_id="t-1", specialist="action", status=status, action_request_id="req-1"
        )


def test_awaiting_approval_needs_request_id():
    with pytest.raises(ValidationError):
        SpecialistReport(
            task_id="t-1",
            specialist="action",
            status="awaiting_approval",
            detail="Waiting for review.",
        )


@pytest.mark.parametrize("rounds", [-1, MAX_TOOL_ROUNDS + 1])
def test_tool_rounds_are_bounded(rounds):
    with pytest.raises(ValidationError):
        SpecialistReport(
            task_id="t-1",
            specialist="research",
            status="completed",
            findings=[FINDING],
            tool_rounds_used=rounds,
        )


def test_report_survives_json_round_trip():
    report = SpecialistReport(
        task_id="t-1",
        specialist=Specialist.ACTION,
        status=ReportStatus.AWAITING_APPROVAL,
        findings=[FINDING],
        detail="Waiting for review.",
        action_request_id="req-1",
        tool_rounds_used=2,
    )
    assert SpecialistReport.model_validate_json(report.model_dump_json()) == report
