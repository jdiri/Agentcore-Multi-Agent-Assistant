import logging

import pytest
from starlette.testclient import TestClient

import support.agent
from common.contracts import Finding, ReportStatus, Specialist, SpecialistReport
from coordinator.runtime import app, get_coordinator

SESSION_HEADER = "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("P3_STUB_ROUTER", "1")
    monkeypatch.delenv("P3_KB_ID", raising=False)  # stub Support, even if set in the shell
    get_coordinator.cache_clear()
    yield TestClient(app)
    get_coordinator.cache_clear()


def test_ping_is_healthy(client):
    response = client.get("/ping")
    assert response.status_code == 200


def test_invocation_returns_reply_and_route(client):
    response = client.post(
        "/invocations",
        json={"prompt": "Summarize my holdings and email my advisor"},
        headers={SESSION_HEADER: "session-123"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["route"] == ["research", "action"]
    assert body["session_id"] == "session-123"
    assert body["refusal"] is None
    assert "[stub research]" in body["reply"]


def test_session_id_is_generated_when_absent(client):
    body = client.post("/invocations", json={"prompt": "What are your fees?"}).json()
    assert body["route"] == ["support"]
    assert body["session_id"]


@pytest.mark.parametrize("payload", [{}, {"prompt": "   "}, {"prompt": 5}])
def test_bad_prompt_is_rejected_before_routing(client, payload):
    assert client.post("/invocations", json=payload).status_code == 400


def test_support_is_the_stub_without_a_kb_id(client, caplog):
    with caplog.at_level(logging.INFO):
        body = client.post("/invocations", json={"prompt": "What are your fees?"}).json()
    assert "[stub support]" in body["reply"]
    assert "support handler: stub" in caplog.text


def test_support_uses_the_knowledge_base_when_kb_id_is_set(client, monkeypatch, caplog):
    async def real_support(task):
        return SpecialistReport(
            task_id=task.task_id,
            specialist=Specialist.SUPPORT,
            status=ReportStatus.COMPLETED,
            findings=[Finding(claim="Fees are listed.", source="Fee Schedule FAQ, 2026-01")],
        )

    monkeypatch.setenv("P3_KB_ID", "KB-TEST")
    monkeypatch.setattr(support.agent, "create_support_handler", lambda: real_support)
    get_coordinator.cache_clear()
    with caplog.at_level(logging.INFO):
        body = client.post("/invocations", json={"prompt": "What are your fees?"}).json()
    assert body["reply"] == "Fees are listed.\n\nSources: [Fee Schedule FAQ, 2026-01]"
    assert "support handler: knowledge base" in caplog.text
    assert "KB-TEST" not in caplog.text
