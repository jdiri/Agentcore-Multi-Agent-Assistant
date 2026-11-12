from langchain_core.tools import tool

from common.contracts.research import GetFundInput


@tool(args_schema=GetFundInput)
async def get_fund(ticker: str) -> str:
    """Retrieve a fund by its ticker symbol."""

    return (
        f"Mock research result for {ticker}. "
        "No verified fund details are available in this mock."
    )

from typing import Any

from langchain_core.tools import tool

from common.contracts.research import (
    GetFundInput,
    GetFundReturnsInput,
    SearchFundsInput,
    GetMyHoldingsInput,
    GetMyAdvisorInput,
)


@tool(args_schema=GetFundInput)
async def get_fund(ticker: str) -> str:
    """Retrieve detailed information about a fund by ticker."""

    return f"MOCK: No verified fund details available for {ticker}."


@tool(args_schema=GetFundReturnsInput)
async def get_fund_returns(
    ticker: str,
    quarters: int | None = None,
) -> str:
    """Retrieve quarterly fund returns by ticker, optionally limited to the last N quarters."""

    return (
        f"MOCK: No verified return data for {ticker}. "
        f"Requested quarters: {quarters}."
    )


@tool(args_schema=SearchFundsInput)
async def search_funds(**filters: Any) -> str:
    """Search funds using structured filters such as asset class, management and expense ratio."""

    return f"MOCK: No verified fund search results. Filters: {filters}"


@tool(args_schema=GetMyHoldingsInput)
async def get_my_holdings() -> str:
    """Retrieve holdings belonging to the authenticated client."""

    return (
        "MOCK: Holdings are unavailable because authenticated "
        "identity and Gateway access are not connected."
    )


@tool(args_schema=GetMyAdvisorInput)
async def get_my_advisor() -> str:
    """Retrieve the authenticated client's assigned advisor."""

    return (
        "MOCK: Advisor information is unavailable because authenticated "
        "identity and Gateway access are not connected."
    )