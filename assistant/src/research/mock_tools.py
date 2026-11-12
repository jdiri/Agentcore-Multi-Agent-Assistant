from langchain_core.tools import tool

from common.contracts.research import GetFundInput


@tool(args_schema=GetFundInput)
async def get_fund(ticker: str) -> str:
    """Retrieve a fund by its ticker symbol."""

    return (
        f"Mock research result for {ticker}. No verified fund details are available in this mock."
    )
