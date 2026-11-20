import asyncio
import importlib.util
from pathlib import Path

from common.contracts import (
    Finding,
    RefusalReason,
    ReportStatus,
    RoutingDecision,
    Specialist,
    SpecialistReport,
)
from common.contracts.support import SUPPORT_GAP_REPLY, gap_report
from coordinator.stubs import STUB_SPECIALISTS, stub_router

CHAT = Path(__file__).resolve().parents[2] / "scripts/chat.py"
spec = importlib.util.spec_from_file_location("chat", CHAT)
chat = importlib.util.module_from_spec(spec)
spec.loader.exec_module(chat)


def stub_session(**overrides):
    return chat.ChatSession(stub_router, {**STUB_SPECIALISTS, **overrides})


def test_session_id_is_kept_across_turns_and_budget_accumulates():
    async def scenario():
        session = stub_session()
        first = await session.ask("What are your fees?")
        second = await session.ask("Summarize my holdings and email my advisor")
        return session, first, second

    session, first, second = asyncio.run(scenario())
    assert len(session.history) == 2
    # Stub reports charge no tool calls; the count is read from the session's own budget.
    assert first.tools_used == second.tools_used == 0
    assert [d.specialist for d in second.decision.delegations] == [
        Specialist.RESEARCH,
        Specialist.ACTION,
    ]


def test_budget_is_charged_per_session_and_new_session_resets_it():
    async def support(task):
        return SpecialistReport(
            task_id=task.task_id,
            specialist=Specialist.SUPPORT,
            status=ReportStatus.COMPLETED,
            findings=[Finding(claim="Three to six business days.", source="ATP v3.2, s.4.1")],
            tool_rounds_used=1,
        )

    async def scenario():
        session = stub_session(**{Specialist.SUPPORT: support})
        await session.ask("q1")
        await session.ask("q2")
        before = await session.tools_used()
        old_id = session.session_id
        session.new_session()
        return before, old_id, session

    before, old_id, session = asyncio.run(scenario())
    assert before == 2
    assert session.session_id != old_id
    assert session.history == []
    assert asyncio.run(session.tools_used()) == 0


def test_message_is_masked_before_the_coordinator_and_transcript_see_it():
    seen = []

    async def support(task):
        seen.append(task.instruction)
        return gap_report(task)

    session = stub_session(**{Specialist.SUPPORT: support})
    turn = asyncio.run(session.ask("Beneficiary for account 7793381504, SSN 123-45-6789?"))
    assert turn.masked
    assert turn.reply == SUPPORT_GAP_REPLY
    for text in (seen[0], turn.message, chat.format_trace(turn)):
        assert "7793381504" not in text and "123-45-6789" not in text
    assert "******1504" in turn.message


def test_trace_shows_route_refusal_status_and_sources():
    async def refuse(message):
        return RoutingDecision(refusal=RefusalReason.INVESTMENT_ADVICE)

    refused = asyncio.run(chat.ChatSession(refuse, dict(STUB_SPECIALISTS)).ask("Should I buy?"))
    assert "refusal: investment_advice" in chat.format_trace(refused)

    turn = asyncio.run(stub_session().ask("What are your fees?"))
    trace = chat.format_trace(turn)
    assert "route: support" in trace
    assert "support: completed, 1 finding(s), sources stub" in trace
    assert "tool calls this session: 0/20" in trace


def test_commands():
    async def scenario():
        session = stub_session()
        state = {"trace": True, "quit": False, "stub": True, "send": None}
        out = {}
        out["examples"] = await chat.handle_command(session, "/examples", state)
        await chat.handle_command(session, "/1", state)
        out["send"] = state["send"]
        out["trace"] = await chat.handle_command(session, "/trace", state)
        out["empty"] = await chat.handle_command(session, "/history", state)
        await session.ask("hello")
        out["history"] = await chat.handle_command(session, "/history", state)
        out["unknown"] = await chat.handle_command(session, "/nope", state)
        await chat.handle_command(session, "/quit", state)
        return state, out

    state, out = asyncio.run(scenario())
    assert "[real mode]" in out["examples"]
    assert out["send"] == chat.EXAMPLES[0][1]
    assert out["trace"] == "  trace off" and state["trace"] is False
    assert out["empty"] == "  (no turns yet)"
    assert "You: hello" in out["history"]
    assert "unknown command" in out["unknown"]
    assert state["quit"] is True


def test_stub_mode_without_kb_id(monkeypatch):
    monkeypatch.delenv("P3_KB_ID", raising=False)
    mode, route, specialists = chat.build_components(stub=False)
    assert mode.startswith("stub") and route is stub_router
    assert set(specialists) == set(Specialist)
