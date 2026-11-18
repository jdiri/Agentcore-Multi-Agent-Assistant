from common.contracts.base import ToolStatus
from common.contracts.research import GetFundReturnsInput
from tools.get_fund_returns_local import get_fund_returns_local


def test_get_last_four_quarters():
    request = GetFundReturnsInput(
        ticker="LFTS1",
        quarters=4,
    )

    result = get_fund_returns_local(request)

    assert result.status == ToolStatus.OK
    assert len(result.data.quarterly_returns) == 4
    assert result.data.quarterly_returns[-1].quarter == "2026-Q3"


def test_get_all_quarters():
    request = GetFundReturnsInput(ticker="LFTS1")

    result = get_fund_returns_local(request)

    assert result.status == ToolStatus.OK
    assert len(result.data.quarterly_returns) == 8


def test_unknown_fund():
    request = GetFundReturnsInput(ticker="UNKNOWN")

    result = get_fund_returns_local(request)

    assert result.status == ToolStatus.NOT_FOUND
    assert result.data is None