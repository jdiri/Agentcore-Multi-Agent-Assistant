import asyncio
from unittest.mock import MagicMock

import pytest

from common.contracts import (
    COORDINATOR_MAX_TOKENS,
    Finding,
    RefusalReason,
    ReportStatus,
    RoutingDecision,
    Specialist,
    SpecialistReport,
    SpecialistTask,
)
from coordinator import router as router_module
from coordinator.graph import REFUSAL_REPLIES, ROUTING_FAILED_REPLY, build_coordinator
from coordinator.stubs import STUB_SPECIALISTS


class Recorder:
    """Records each task and returns the scripted status for its specialist."""

    def __init__(self, statuses=None, failing=()):
        self.tasks: list[SpecialistTask] = []
        self.statuses = statuses or {}
        self.failing = set(failing)
        self.handlers = {specialist: self._handler(specialist) for specialist in Specialist}

    def _handler(self, specialist):
        async def handle(task):
            self.tasks.append(task)
            if specialist in self.failing:
                raise TimeoutError("secret detail")
            status = self.statuses.get(specialist, ReportStatus.COMPLETED)
            if status is ReportStatus.COMPLETED:
                finding = Finding(claim=f"{specialist} claim", source=f"{specialist} source")
                return SpecialistReport(
                    task_id=task.task_id, specialist=specialist, status=status, findings=[finding]
                )
            return SpecialistReport(
                task_id=task.task_id,
                specialist=specialist,
                status=status,
                detail=f"{specialist} {status}",
                action_request_id="req-1",
            )

        return handle

    @property
    def called(self):
        return [task.specialist.value for task in self.tasks]


def run(decision, recorder=None):
    recorder = recorder or Recorder()

    async def route(_message):
        if isinstance(decision, Exception):
            raise decision
        return decision

    graph = build_coordinator(route, recorder.handlers)
    state = {"message": "hello", "session_id": "s-1", "turn_id": "turn-1"}
    return asyncio.run(graph.ainvoke(state)), recorder


def plan(*specialists):
    return RoutingDecision(
        delegations=[{"specialist": s, "task": f"{s} task"} for s in specialists]
    )


def test_specialists_run_in_planned_order():
    result, recorder = run(plan("research", "action"))
    assert recorder.called == ["research", "action"]
    assert "research claim" in result["reply"] and "action claim" in result["reply"]


def test_specialist_gets_only_its_task_and_earlier_findings():
    _, recorder = run(plan("research", "action"))
    assert recorder.tasks[0].instruction == "research task"
    assert recorder.tasks[0].prior_findings == ()
    assert [f.claim for f in recorder.tasks[1].prior_findings] == ["research claim"]
    assert recorder.tasks[1].session_id == "s-1" and recorder.tasks[1].turn_id == "turn-1"


def test_four_handoffs_all_run():
    decision = RoutingDecision(
        delegations=[
            {"specialist": "research", "task": "one"},
            {"specialist": "support", "task": "two"},
            {"specialist": "action", "task": "three"},
            {"specialist": "research", "task": "four", "repeat_justification": "needed again"},
        ]
    )
    _, recorder = run(decision)
    assert recorder.called == ["research", "support", "action", "research"]


@pytest.mark.parametrize("reason", list(RefusalReason))
def test_refusal_calls_no_specialist(reason):
    result, recorder = run(RoutingDecision(refusal=reason))
    assert recorder.called == []
    assert result["reply"] == REFUSAL_REPLIES[reason]


def test_routing_failure_is_reported_without_crashing():
    result, recorder = run(ValueError("bad output"))
    assert recorder.called == []
    assert result["reply"] == ROUTING_FAILED_REPLY


def test_awaiting_approval_ends_the_turn():
    recorder = Recorder(statuses={Specialist.ACTION: ReportStatus.AWAITING_APPROVAL})
    result, recorder = run(plan("action", "support"), recorder)
    assert recorder.called == ["action"]
    assert "awaiting_approval" in result["reply"]


def test_action_is_not_started_after_an_incomplete_step():
    recorder = Recorder(statuses={Specialist.RESEARCH: ReportStatus.TOOL_FAILED})
    result, recorder = run(plan("research", "action"), recorder)
    assert recorder.called == ["research"]
    assert "did not start the requested action" in result["reply"]


def test_independent_step_still_runs_after_a_failure():
    recorder = Recorder(statuses={Specialist.SUPPORT: ReportStatus.NO_INFORMATION})
    _, recorder = run(plan("support", "research"), recorder)
    assert recorder.called == ["support", "research"]


def test_crashed_specialist_degrades_without_leaking_the_error():
    recorder = Recorder(failing=[Specialist.ACTION])
    result, recorder = run(plan("support", "action"), recorder)
    assert "support claim" in result["reply"]
    assert "couldn't complete the action part" in result["reply"]
    assert "secret detail" not in result["reply"]


def test_support_reply_uses_the_required_sources_line():
    result, _ = run(plan("support"))
    assert result["reply"].endswith("Sources: [support source]")


def test_research_reply_does_not_cite_tool_names():
    result, _ = run(plan("research"))
    assert "Sources:" not in result["reply"]


def test_missing_specialist_handler_fails_at_build():
    partial = {Specialist.SUPPORT: STUB_SPECIALISTS[Specialist.SUPPORT]}
    with pytest.raises(ValueError, match="missing specialist handlers"):
        build_coordinator(MagicMock(), partial)


def test_bedrock_router_applies_token_cap_and_structured_output(monkeypatch):
    model_class = MagicMock()
    monkeypatch.setattr(router_module, "ChatBedrockConverse", model_class)
    router_module.create_bedrock_router()
    assert model_class.call_args.kwargs["max_tokens"] == COORDINATOR_MAX_TOKENS
    model_class.return_value.with_structured_output.assert_called_once_with(RoutingDecision)
