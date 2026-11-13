import asyncio
import importlib.util
from pathlib import Path

from common.contracts import Finding, ReportStatus, Specialist, SpecialistReport
from common.contracts.support import SUPPORT_GAP_REPLY, gap_report

DEMO = Path(__file__).resolve().parents[2] / "scripts/demo.py"
spec = importlib.util.spec_from_file_location("demo", DEMO)
demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(demo)


def test_router_sends_every_question_to_support():
    decision = asyncio.run(demo.support_router("Show my fund balance and email it"))
    assert [d.specialist for d in decision.delegations] == [Specialist.SUPPORT]


def test_demo_uses_the_given_support_handler_and_renders_sources():
    async def support(task):
        return SpecialistReport(
            task_id=task.task_id,
            specialist=Specialist.SUPPORT,
            status=ReportStatus.COMPLETED,
            findings=[Finding(claim="It takes 3 to 6 business days.", source="ATP v3.2, s.4.1")],
        )

    reply = asyncio.run(demo.ask(demo.build_demo_coordinator(support), "q"))
    assert reply == "It takes 3 to 6 business days.\n\nSources: [ATP v3.2, s.4.1]"


def test_demo_shows_the_exact_gap_reply():
    async def support(task):
        return gap_report(task)

    assert asyncio.run(demo.ask(demo.build_demo_coordinator(support), "q")) == SUPPORT_GAP_REPLY
