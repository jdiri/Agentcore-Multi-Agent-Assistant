"""Stand-ins so the Coordinator runs before the real specialists exist.

Each owner replaces their entry in `STUB_SPECIALISTS` with a real `SpecialistHandler`.
`stub_router` lets the graph run locally with no AWS access.
"""

import asyncio
from collections.abc import Mapping

from common.contracts import (
    Delegation,
    Finding,
    ReportStatus,
    RoutingDecision,
    Specialist,
    SpecialistReport,
    SpecialistTask,
)
from coordinator.graph import SpecialistHandler

from .action_client import ask_action_agent

_RESEARCH_WORDS = ("holding", "fund", "balance", "advisor?")
_ACTION_WORDS = ("ticket", "email", "send", "notify")


def _stub(specialist: Specialist) -> SpecialistHandler:
    async def handle(task: SpecialistTask) -> SpecialistReport:
        return SpecialistReport(
            task_id=task.task_id,
            specialist=specialist,
            status=ReportStatus.COMPLETED,
            findings=[Finding(claim=f"[stub {specialist}] {task.instruction}", source="stub")],
        )

    return handle


async def action_handler(task: SpecialistTask) -> SpecialistReport:
    response = await asyncio.to_thread(ask_action_agent, task.instruction)

    return SpecialistReport(
        task_id=task.task_id,
        specialist=Specialist.ACTION,
        status=ReportStatus.COMPLETED,
        findings=[Finding(claim=response, source="Action Agent")],
    )


STUB_SPECIALISTS: Mapping[Specialist, SpecialistHandler] = {
    # specialist: _stub(specialist) for specialist in Specialist
    Specialist.RESEARCH: _stub(Specialist.RESEARCH),
    Specialist.SUPPORT: _stub(Specialist.SUPPORT),
    Specialist.ACTION: action_handler,
}


async def stub_router(message: str) -> RoutingDecision:
    text = message.lower()
    route = []
    if any(word in text for word in _RESEARCH_WORDS):
        route.append(Specialist.RESEARCH)
    if any(word in text for word in _ACTION_WORDS):
        route.append(Specialist.ACTION)
    return RoutingDecision(
        delegations=[
            Delegation(specialist=specialist, task=message)
            for specialist in route or [Specialist.SUPPORT]
        ]
    )
