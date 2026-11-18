from common.contracts.base import ToolStatus
from common.contracts.research import (
    FundReturns,
    GetFundInput,
    GetFundReturnsInput,
    GetFundReturnsOutput,
)

from tools.get_fund_local import get_fund_local


def get_fund_returns_local(
    request: GetFundReturnsInput,
) -> GetFundReturnsOutput:

    # Reuse existing fund retrieval
    fund_result = get_fund_local(
        GetFundInput(ticker=request.ticker)
    )

    # Fund doesn't exist
    if fund_result.status == ToolStatus.NOT_FOUND:
        return GetFundReturnsOutput(
            status=ToolStatus.NOT_FOUND
        )

    # Propagate retrieval errors
    if fund_result.status == ToolStatus.ERROR:
        return GetFundReturnsOutput(
            status=ToolStatus.ERROR,
            error=fund_result.error,
        )

    fund = fund_result.data

    # Returns are in chronological order
    returns = fund.quarterly_returns

    # Select the most recent N quarters
    if request.quarters is not None:
        returns = returns[-request.quarters:]

    return GetFundReturnsOutput(
        status=ToolStatus.OK,
        data=FundReturns(
            ticker=fund.ticker,
            quarterly_returns=returns,
        ),
    )