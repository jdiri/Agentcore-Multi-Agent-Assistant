
# src/services/research_service.py

from common.contracts.base import ToolStatus
from common.contracts.research import (
    Fund,
    FundReturns,
    Holding,
    Advisor,
    GetFundInput,
    GetFundReturnsInput,
    SearchFundsInput,
    GetMyHoldingsInput,
    GetMyAdvisorInput,
    GetFundOutput,
    GetFundReturnsOutput,
    SearchFundsOutput,
    GetMyHoldingsOutput,
    GetMyAdvisorOutput,
)


class ResearchService:
    def __init__(self, repository):
        self.repository = repository

    # 1. Retrieve a fund
    def get_fund(
        self, request: GetFundInput
    ) -> GetFundOutput:

        item = self.repository.get_fund(request.ticker)

        if item is None:
            return GetFundOutput(
                status=ToolStatus.NOT_FOUND
            )

        return GetFundOutput(
            status=ToolStatus.OK,
            data=Fund.model_validate(item)
        )

    # 2. Retrieve quarterly returns
    def get_fund_returns(
        self, request: GetFundReturnsInput
    ) -> GetFundReturnsOutput:

        item = self.repository.get_fund(request.ticker)

        if item is None:
            return GetFundReturnsOutput(
                status=ToolStatus.NOT_FOUND
            )

        fund = Fund.model_validate(item)

        # Ensure quarters are ordered chronologically.
        returns = sorted(
            fund.quarterly_returns,
            key=lambda entry: entry.quarter
        )

        if request.quarters is not None:
            returns = returns[-request.quarters:]

        return GetFundReturnsOutput(
            status=ToolStatus.OK,
            data=FundReturns(
                ticker=fund.ticker,
                quarterly_returns=tuple(returns)
            )
        )

    # 3. Search funds using named filters
    def search_funds(
        self, request: SearchFundsInput
    ) -> SearchFundsOutput:

        records = self.repository.list_funds()
        funds = [Fund.model_validate(r) for r in records]

        filtered = []

        # These filters must all match (AND logic).
        for fund in funds:

            if request.asset_class is not None:
                if fund.asset_class.casefold() != request.asset_class.casefold():
                    continue

            if request.management is not None:
                if fund.management != request.management:
                    continue

            if request.name_contains is not None:
                if request.name_contains.casefold() not in fund.name.casefold():
                    continue

            ranges = (
                (request.min_expense_ratio, fund.expense_ratio_pct, request.max_expense_ratio),
                (request.min_nav_usd, fund.nav_usd, request.max_nav_usd),
                (
                    request.min_initial_investment_usd,
                    fund.minimum_initial_investment_usd,
                    request.max_initial_investment_usd,
                ),
                (request.inception_date_from, fund.inception_date, request.inception_date_to),
                (request.nav_as_of_from, fund.nav_as_of, request.nav_as_of_to),
            )

            if any(
                (minimum is not None and value < minimum)
                or (maximum is not None and value > maximum)
                for minimum, value, maximum in ranges
            ):
                continue

            filtered.append(fund)

        filtered.sort(key=lambda fund: fund.ticker)

        return SearchFundsOutput(
            status=ToolStatus.OK,
            data=filtered
        )

    # 4. Retrieve signed-in user's holdings
    def get_my_holdings(
        self,
        request: GetMyHoldingsInput,
        *,
        user_id: str
    ) -> GetMyHoldingsOutput:

        # user_id MUST come from verified backend identity.
        if not user_id:
            raise ValueError("Verified user identity is required")

        records = self.repository.get_holdings_by_user(user_id)

        holdings = [
            Holding.model_validate({
                "account_type": record["account_type"],
                "ticker": record["ticker"],
                "shares": record["shares"],
                "market_value_usd": record["market_value_usd"],
                "as_of": record["as_of"],
            })
            for record in records
        ]

        return GetMyHoldingsOutput(
            status=ToolStatus.OK,
            data=holdings
        )

    # 5. Retrieve signed-in user's advisor
    def get_my_advisor(
        self,
        request: GetMyAdvisorInput,
        *,
        user_id: str
    ) -> GetMyAdvisorOutput:

        if not user_id:
            raise ValueError("Verified user identity is required")

        user = self.repository.get_user(user_id)

        if user is None:
            return GetMyAdvisorOutput(
                status=ToolStatus.NOT_FOUND
            )

        advisor_id = user["advisor_id"]

        advisor = self.repository.get_advisor(advisor_id)

        if advisor is None:
            return GetMyAdvisorOutput(
                status=ToolStatus.NOT_FOUND
            )

        return GetMyAdvisorOutput(
            status=ToolStatus.OK,
            data=Advisor.model_validate({
                "advisor_id": advisor["advisor_id"],
                "name": advisor["name"],
                "email": advisor["email"],
            })
        )
