from common.contracts.base import ToolStatus
from common.contracts.research import GetFundInput
from tools.get_fund_local import get_fund_local


def test_existing_fund():
    result = get_fund_local(GetFundInput(ticker="LFTS1"))

    assert result.status == ToolStatus.OK
    assert result.data.ticker == "LFTS1"
    assert len(result.data.quarterly_returns) == 8


def test_unknown_fund():
    result = get_fund_local(GetFundInput(ticker="UNKNOWN"))

    assert result.status == ToolStatus.NOT_FOUND
    assert result.data is None
