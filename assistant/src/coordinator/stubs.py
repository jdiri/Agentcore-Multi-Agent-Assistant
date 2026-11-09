"""Stand-ins so the Coordinator runs before the real specialists exist.

Each owner replaces their entry in `STUB_SPECIALISTS` with a real `SpecialistHandler`.
`stub_router` lets the graph run locally with no AWS access.
"""

from collections.abc import Mapping

from assistant.src.common.contracts import (
    Delegation,
    Finding,
    ReportStatus,
    RoutingDecision,
    Specialist,
    SpecialistReport,
    SpecialistTask,
)
from assistant.src.coordinator.graph import SpecialistHandler

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


STUB_SPECIALISTS: Mapping[Specialist, SpecialistHandler] = {
    specialist: _stub(specialist) for specialist in Specialist
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
