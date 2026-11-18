import asyncio
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError, ReadTimeoutError

from common.bedrock import MAX_ATTEMPTS
from common.contracts import (
    COORDINATOR_MAX_TOKENS,
    MAX_TOOL_CALLS_PER_CONVERSATION,
    Finding,
    RefusalReason,
    ReportStatus,
    RoutingDecision,
    Specialist,
    SpecialistReport,
    SpecialistTask,
)
from coordinator import router as router_module
from coordinator.budget import InMemoryToolBudget
from coordinator.graph import (
    BUSY_REPLY,
    REFUSAL_REPLIES,
    ROUTING_FAILED_REPLY,
    STOPPED_REPLY,
    build_coordinator,
)
from coordinator.stubs import STUB_SPECIALISTS


class Recorder:
    """Records each task and returns the scripted status for its specialist."""

    def __init__(self, statuses=None, failing=(), tool_calls=0, tamper=None):
        self.tasks: list[SpecialistTask] = []
        self.statuses = statuses or {}
        self.failing = set(failing)
        self.tool_calls = tool_calls
        self.tamper = tamper or {}  # specialist -> fields to overwrite on its report
        self.handlers = {specialist: self._handler(specialist) for specialist in Specialist}

    def _handler(self, specialist):
        async def handle(task):
            self.tasks.append(task)
            if specialist in self.failing:
                raise TimeoutError("secret detail")
            status = self.statuses.get(specialist, ReportStatus.COMPLETED)
            fields = {
                "task_id": task.task_id,
                "specialist": specialist,
                "status": status,
                "tool_calls_used": self.tool_calls,
            }
            if status is ReportStatus.COMPLETED:
                fields["findings"] = [
                    Finding(claim=f"{specialist} claim", source=f"{specialist} source")
                ]
            else:
                fields["detail"] = f"{specialist} {status}"
                fields["action_request_id"] = "req-1"
            fields.update(self.tamper.get(specialist, {}))
            return SpecialistReport(**fields)

        return handle

    @property
    def called(self):
        return [task.specialist.value for task in self.tasks]


def build(decision, recorder, budget=None):
    async def route(_message):
        if isinstance(decision, Exception):
            raise decision
        return decision

    return build_coordinator(route, recorder.handlers, budget)


def turn(graph, session_id="s-1", turn_id="turn-1"):
    state = {"message": "hello", "session_id": session_id, "turn_id": turn_id}
    return asyncio.run(graph.ainvoke(state))


def run(decision, recorder=None, budget=None):
    recorder = recorder or Recorder()
    return turn(build(decision, recorder, budget)), recorder


def throttling_error():
    return ClientError(
        {"Error": {"Code": "ThrottlingException", "Message": "slow down"}}, "Converse"
    )


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


@pytest.mark.parametrize(
    "tamper", [{"task_id": "someone-elses-task"}, {"specialist": Specialist.SUPPORT}]
)
def test_mismatched_report_is_rejected_and_its_findings_dropped(tamper, caplog):
    recorder = Recorder(tamper={Specialist.RESEARCH: tamper})
    result, _ = run(plan("research"), recorder)
    assert "research claim" not in result["reply"]
    assert "support claim" not in result["reply"]
    assert "couldn't complete the research part" in result["reply"]
    assert "report rejected" in caplog.text and "ProtocolViolation" in caplog.text


def test_ceiling_reached_stops_before_the_next_specialist():
    budget = InMemoryToolBudget()
    asyncio.run(budget.add("s-1", MAX_TOOL_CALLS_PER_CONVERSATION))
    result, recorder = run(plan("research", "action"), budget=budget)
    assert recorder.called == []
    assert result["reply"] == STOPPED_REPLY


def test_ceiling_reached_mid_turn_keeps_earlier_findings_and_skips_the_rest():
    recorder = Recorder(tool_calls=MAX_TOOL_CALLS_PER_CONVERSATION)
    result, recorder = run(plan("research", "action"), recorder)
    assert recorder.called == ["research"]
    assert result["reply"].startswith("research claim")
    assert result["reply"].endswith(STOPPED_REPLY)


def test_ceiling_counts_across_turns_in_one_session_only():
    recorder = Recorder(tool_calls=MAX_TOOL_CALLS_PER_CONVERSATION // 2)
    graph = build(plan("research"), recorder)
    for number in range(2):
        assert turn(graph, turn_id=f"turn-{number}")["reply"] == "research claim"
    assert turn(graph, turn_id="turn-3")["reply"] == STOPPED_REPLY
    assert turn(graph, session_id="s-2")["reply"] == "research claim"
    assert len(recorder.tasks) == 3


def test_tool_rounds_count_when_a_specialist_does_not_report_calls():
    budget = InMemoryToolBudget()
    recorder = Recorder(tamper={Specialist.SUPPORT: {"tool_rounds_used": 2}})
    run(plan("support"), recorder, budget)
    assert asyncio.run(budget.used("s-1")) == 2


def test_rejected_report_still_charges_its_calls():
    budget = InMemoryToolBudget()
    recorder = Recorder(tool_calls=3, tamper={Specialist.RESEARCH: {"task_id": "other"}})
    run(plan("research"), recorder, budget)
    assert asyncio.run(budget.used("s-1")) == 3


@pytest.mark.parametrize(
    "error", [throttling_error(), ReadTimeoutError(endpoint_url="https://bedrock"), TimeoutError()]
)
def test_throttled_or_timed_out_routing_says_busy(error):
    result, recorder = run(error)
    assert recorder.called == []
    assert result["reply"] == BUSY_REPLY


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
    config = model_class.call_args.kwargs["config"]
    assert config.retries == {"max_attempts": MAX_ATTEMPTS, "mode": "standard"}
    assert config.read_timeout and config.connect_timeout


def test_router_prompt_names_every_specialist_and_refusal():
    prompt = router_module.SYSTEM_PROMPT
    for value in [*Specialist, *RefusalReason]:
        assert f"{value.value}:" in prompt, value


def _router_with_outcomes(monkeypatch, outcomes):
    """A Bedrock router whose structured model returns or raises each outcome in turn."""
    calls = []

    async def ainvoke(messages):
        calls.append(messages)
        outcome = outcomes[len(calls) - 1]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    model_class = MagicMock()
    model_class.return_value.with_structured_output.return_value.ainvoke = ainvoke
    monkeypatch.setattr(router_module, "ChatBedrockConverse", model_class)
    return router_module.create_bedrock_router(), calls


def test_bedrock_router_retries_once_after_a_bad_answer(monkeypatch):
    decision = RoutingDecision(refusal=RefusalReason.OFF_TOPIC)
    route, calls = _router_with_outcomes(monkeypatch, [ValueError("bad plan"), decision])
    assert asyncio.run(route("hi")) == decision
    assert len(calls) == 2


def test_bedrock_router_gives_up_after_bounded_attempts(monkeypatch):
    failures = [ValueError("bad plan")] * router_module.ROUTING_ATTEMPTS
    route, calls = _router_with_outcomes(monkeypatch, failures)
    with pytest.raises(ValueError):
        asyncio.run(route("hi"))
    assert len(calls) == router_module.ROUTING_ATTEMPTS


def test_bedrock_router_leaves_throttling_retries_to_botocore(monkeypatch):
    decision = RoutingDecision(refusal=RefusalReason.OFF_TOPIC)
    route, calls = _router_with_outcomes(monkeypatch, [throttling_error(), decision])
    with pytest.raises(ClientError):
        asyncio.run(route("hi"))
    assert len(calls) == 1
