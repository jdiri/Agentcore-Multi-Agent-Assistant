
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from tools import research_lambda


def gateway_context(tool_name: str):
    return SimpleNamespace(
        client_context=SimpleNamespace(
            custom={
                "bedrockAgentCoreToolName":
                    f"catalog-read___{tool_name}"
            }
        )
    )


@pytest.fixture
def fake_tools(monkeypatch):
    tools = MagicMock()
    monkeypatch.setattr(
        research_lambda,
        "get_tools",
        lambda: tools,
    )
    return tools


def test_get_fund(fake_tools):
    fake_tools.get_fund.return_value = {
        "status": "ok"
    }

    result = research_lambda.lambda_handler(
        {"ticker": "LFTS1"},
        gateway_context("get_fund"),
    )

    fake_tools.get_fund.assert_called_once_with(
        ticker="LFTS1"
    )

    assert result["status"] == "ok"


def test_get_fund_returns(fake_tools):
    fake_tools.get_fund_returns.return_value = {
        "status": "ok"
    }

    research_lambda.lambda_handler(
        {"ticker": "LFTS1", "quarters": 2},
        gateway_context("get_fund_returns"),
    )

    fake_tools.get_fund_returns.assert_called_once_with(
        ticker="LFTS1",
        quarters=2,
    )


def test_invalid_arguments(fake_tools):
    result = research_lambda.lambda_handler(
        {"ticker": "LFTS1", "user_id": "u-002"},
        gateway_context("get_fund"),
    )

    assert result == {
        "error": "Invalid tool arguments"
    }
    fake_tools.get_fund.assert_not_called()


def test_private_tool_blocked(fake_tools):
    result = research_lambda.lambda_handler(
        {},
        gateway_context("get_my_holdings"),
    )

    assert result == {
        "error": "Unsupported tool"
    }
    fake_tools.get_my_holdings.assert_not_called()
