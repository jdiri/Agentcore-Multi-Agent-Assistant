import pytest
from starlette.testclient import TestClient

from coordinator.runtime import app, get_coordinator

SESSION_HEADER = "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("P3_STUB_ROUTER", "1")
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
