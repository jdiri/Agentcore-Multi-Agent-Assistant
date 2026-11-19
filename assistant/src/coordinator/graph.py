"""Coordinator graph for Runtime #1: route, run specialists in order, compose the reply.

The Coordinator has no tools and only writes from specialist reports. Task text is not logged.
If it ever is, mask it first with `common.masking.mask_sensitive`; the runtime's log handler
also masks every line as a backstop.
"""

import logging
import uuid
from collections.abc import Awaitable, Callable, Mapping
from operator import add
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph

from common.bedrock import is_busy_error
from common.contracts import (
    MAX_TOOL_CALLS_PER_CONVERSATION,
    Delegation,
    Finding,
    RefusalReason,
    ReportStatus,
    RoutingDecision,
    Specialist,
    SpecialistReport,
    SpecialistTask,
)
from common.contracts.protocol import ProtocolViolation, verify_report
from coordinator.budget import InMemoryToolBudget, ToolBudget

logger = logging.getLogger(__name__)

Router = Callable[[str], Awaitable[RoutingDecision]]
SpecialistHandler = Callable[[SpecialistTask], Awaitable[SpecialistReport]]

ROUTING_FAILED_REPLY = "I'm sorry, I couldn't process that request just now. Please try again."
BUSY_REPLY = "I'm busy right now and couldn't process that request. Please try again in a moment."
STOPPED_REPLY = (
    "I stopped here because this conversation reached its limit on lookups. "
    "Please start a new conversation, or I can open a ticket for you."
)
REFUSAL_REPLIES: Mapping[RefusalReason, str] = {
    RefusalReason.OFF_TOPIC: (
        "I can only help with questions about your Lanternfield accounts, funds and policies."
    ),
    RefusalReason.INVESTMENT_ADVICE: (
        "I can't give investment advice, but I can ask your advisor to reach out. "
        "Would you like me to do that?"
    ),
    RefusalReason.PROMPT_ATTACK: "I can't help with that request.",
    RefusalReason.CROSS_CLIENT: "I can only share information about your own accounts.",
}


class TurnState(TypedDict, total=False):
    message: str
    session_id: str
    turn_id: str
    decision: RoutingDecision | None
    reports: Annotated[list[SpecialistReport], add]
    routing_busy: bool  # routing failed on throttling or a timeout
    stopped: bool  # the conversation's tool-call ceiling was reached
    reply: str


def _next_step(state: TurnState) -> str:
    decision = state.get("decision")
    reports = state.get("reports", [])
    if decision is None or state.get("stopped") or len(reports) >= len(decision.delegations):
        return "compose"
    if reports and reports[-1].status is ReportStatus.AWAITING_APPROVAL:
        return "compose"
    return "run_specialist"


def _render_reply(
    decision: RoutingDecision | None,
    reports: list[SpecialistReport],
    *,
    routing_busy: bool = False,
    stopped: bool = False,
) -> str:
    if decision is None:
        return BUSY_REPLY if routing_busy else ROUTING_FAILED_REPLY
    if decision.refusal is not None:
        return REFUSAL_REPLIES[decision.refusal]

    parts: list[str] = []
    for report in reports:
        parts.extend(finding.claim for finding in report.findings)
        if report.detail:
            parts.append(report.detail)
        if report.specialist is Specialist.SUPPORT and report.findings:
            sources = dict.fromkeys(finding.source for finding in report.findings)
            parts.append("Sources: " + " ".join(f"[{source}]" for source in sources))
    if stopped:
        parts.append(STOPPED_REPLY)
    return "\n\n".join(parts)


def build_coordinator(
    route: Router,
    specialists: Mapping[Specialist, SpecialistHandler],
    budget: ToolBudget | None = None,
):
    """Compile the graph. `specialists` must have a handler for every `Specialist`.

    `budget` counts tool calls per session against `MAX_TOOL_CALLS_PER_CONVERSATION`. The
    ceiling is checked before each delegation, so one specialist can overshoot it by at most
    its own calls (bounded by its tool rounds).
    """
    missing = set(Specialist) - set(specialists)
    if missing:
        raise ValueError(f"missing specialist handlers: {sorted(missing)}")
    budget = budget if budget is not None else InMemoryToolBudget()

    async def route_node(state: TurnState) -> TurnState:
        try:
            return {"decision": await route(state["message"])}
        except Exception as exc:
            # Type only: validation errors can echo the client's message.
            logger.error("routing failed turn_id=%s error=%s", state["turn_id"], type(exc).__name__)
            return {"decision": None, "routing_busy": is_busy_error(exc)}

    async def run_specialist(state: TurnState) -> TurnState:
        reports = state.get("reports", [])
        delegation: Delegation = state["decision"].delegations[len(reports)]

        used = await budget.used(state["session_id"])
        if used >= MAX_TOOL_CALLS_PER_CONVERSATION:
            logger.warning(
                "tool ceiling reached turn_id=%s specialist=%s used=%d limit=%d",
                state["turn_id"],
                delegation.specialist,
                used,
                MAX_TOOL_CALLS_PER_CONVERSATION,
            )
            return {"stopped": True}

        # Never let Action draft or send from incomplete inputs.
        if delegation.specialist is Specialist.ACTION and any(
            report.status is not ReportStatus.COMPLETED for report in reports
        ):
            return {"reports": [_not_started_report()]}

        prior_findings: tuple[Finding, ...] = tuple(
            finding
            for report in reports
            if report.status is ReportStatus.COMPLETED
            for finding in report.findings
        )
        task = SpecialistTask(
            task_id=str(uuid.uuid4()),
            session_id=state["session_id"],
            turn_id=state["turn_id"],
            specialist=delegation.specialist,
            instruction=delegation.task,
            prior_findings=prior_findings,
        )
        logger.info(
            "delegating turn_id=%s task_id=%s specialist=%s",
            task.turn_id,
            task.task_id,
            task.specialist,
        )
        try:
            report = await specialists[task.specialist](task)
        except Exception as exc:
            logger.error(
                "specialist failed task_id=%s specialist=%s error=%s",
                task.task_id,
                task.specialist,
                type(exc).__name__,
            )
            return {"reports": [_unreachable_report(task)]}

        # Charge the calls even if the report is rejected below: they were still made.
        await budget.add(state["session_id"], report.tool_calls_charged)
        try:
            return {"reports": [verify_report(task, report)]}
        except ProtocolViolation as exc:
            logger.error(
                "report rejected task_id=%s specialist=%s error=%s",
                task.task_id,
                task.specialist,
                type(exc).__name__,
            )
            return {"reports": [_unreachable_report(task)]}

    def compose(state: TurnState) -> TurnState:
        reply = _render_reply(
            state.get("decision"),
            state.get("reports", []),
            routing_busy=state.get("routing_busy", False),
            stopped=state.get("stopped", False),
        )
        return {"reply": reply}

    graph = StateGraph(TurnState)
    graph.add_node("route", route_node)
    graph.add_node("run_specialist", run_specialist)
    graph.add_node("compose", compose)
    graph.add_edge(START, "route")
    graph.add_conditional_edges("route", _next_step, ["run_specialist", "compose"])
    graph.add_conditional_edges("run_specialist", _next_step, ["run_specialist", "compose"])
    graph.add_edge("compose", END)
    return graph.compile()


def _not_started_report() -> SpecialistReport:
    return SpecialistReport(
        task_id=str(uuid.uuid4()),
        specialist=Specialist.ACTION,
        status=ReportStatus.UNAVAILABLE,
        detail="I did not start the requested action because an earlier step did not complete.",
    )


def _unreachable_report(task: SpecialistTask) -> SpecialistReport:
    return SpecialistReport(
        task_id=task.task_id,
        specialist=task.specialist,
        status=ReportStatus.UNAVAILABLE,
        detail=f"I couldn't complete the {task.specialist} part of your request right now.",
    )
