
# src/tools/research_tools.py

from common.contracts.research import (
    GetFundInput,
    GetFundReturnsInput,
    SearchFundsInput,
    GetMyHoldingsInput,
    GetMyAdvisorInput,
)

from research.service import ResearchService


class ResearchTools:
    def __init__(self, service: ResearchService):
        self.service = service

    # 1. Get fund information
    def get_fund(self, ticker: str) -> dict:
        request = GetFundInput(ticker=ticker)

        result = self.service.get_fund(request)

        return result.model_dump(mode="json")

    # 2. Get quarterly fund returns
    def get_fund_returns(
        self,
        ticker: str,
        quarters: int | None = None,
    ) -> dict:

        request = GetFundReturnsInput(
            ticker=ticker,
            quarters=quarters,
        )

        result = self.service.get_fund_returns(request)

        return result.model_dump(mode="json")

    # 3. Search funds by named filters
    def search_funds(self, **filters) -> dict:
        request = SearchFundsInput.model_validate(filters)

        result = self.service.search_funds(request)

        return result.model_dump(mode="json")

    # 4. Get the authenticated user's holdings
    def get_my_holdings(
        self,
        *,
        verified_user_id: str,
    ) -> dict:

        request = GetMyHoldingsInput()

        result = self.service.get_my_holdings(
            request,
            user_id=verified_user_id,
        )

        return result.model_dump(mode="json")

    # 5. Get the authenticated user's advisor
    def get_my_advisor(
        self,
        *,
        verified_user_id: str,
    ) -> dict:

        request = GetMyAdvisorInput()

        result = self.service.get_my_advisor(
            request,
            user_id=verified_user_id,
        )

        return result.model_dump(mode="json")
