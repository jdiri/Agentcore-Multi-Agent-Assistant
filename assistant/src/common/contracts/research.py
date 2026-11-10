"""Research's five read-only Gateway tool I/O schemas.

Only AgentCore/Lambda receives verified user identity (never a model tool parameter).
The fund ticker uniquely identifies a fund in the provided synthetic corpus.
"""

from datetime import date
from decimal import Decimal
from typing import Literal, Self

from pydantic import Field, model_validator

from .base import StrictContract, ToolResult
from .routing import NonBlank


class QuarterlyReturn(StrictContract):
    quarter: str = Field(pattern=r"^\d{4}-Q[1-4]$")
    total_return_pct: Decimal


class Fund(StrictContract):
    ticker: NonBlank
    name: NonBlank
    asset_class: NonBlank
    management: Literal["Index", "Active"]
    expense_ratio_pct: Decimal = Field(ge=0)
    minimum_initial_investment_usd: Decimal = Field(ge=0)
    inception_date: date
    nav_usd: Decimal = Field(ge=0)
    nav_as_of: date
    description: NonBlank
    quarterly_returns: tuple[QuarterlyReturn, ...]
    synthetic: Literal[True]


class FundReturns(StrictContract):
    ticker: NonBlank
    quarterly_returns: tuple[QuarterlyReturn, ...]


class Holding(StrictContract):
    account_type: NonBlank
    ticker: NonBlank
    shares: Decimal = Field(ge=0)
    market_value_usd: Decimal = Field(ge=0)
    as_of: date
    # account_number and user_id deliberately excluded from tool output


class Advisor(StrictContract):
    advisor_id: NonBlank
    name: NonBlank
    email: NonBlank
    # verify_in_ses is internal setup data, not a permission grant


class GetFundInput(StrictContract):
    ticker: NonBlank


class GetFundReturnsInput(StrictContract):
    ticker: NonBlank
    quarters: int | None = Field(default=None, ge=1, le=8)
    # Proposed semantics: last N quarters. None returns all available.
    # Brief mentions 'quarters' but does not define its type.


class SearchFundsInput(StrictContract):
    """Filters are optional individually, but at least one must be provided.

    'max_expense_ratio' is the name in the blueprint, measured in percentage
    points: 0.10 means 0.10%, not a 10% fraction.
    Other filters are proposed expansions from the team's Research discussion.
    """

    asset_class: NonBlank | None = None
    management: Literal["Index", "Active"] | None = None
    name_contains: str | None = Field(default=None, min_length=2, max_length=80)
    max_expense_ratio: Decimal | None = Field(default=None, ge=0)
    min_expense_ratio: Decimal | None = Field(default=None, ge=0)
    min_nav_usd: Decimal | None = Field(default=None, ge=0)
    max_nav_usd: Decimal | None = Field(default=None, ge=0)
    min_initial_investment_usd: Decimal | None = Field(default=None, ge=0)
    max_initial_investment_usd: Decimal | None = Field(default=None, ge=0)
    inception_date_from: date | None = None
    inception_date_to: date | None = None
    nav_as_of_from: date | None = None
    nav_as_of_to: date | None = None

    @model_validator(mode="after")
    def valid_filters(self) -> Self:
        if not any(value is not None for value in self.model_dump().values()):
            raise ValueError("At least one named search filter is required")
        pairs = (
            ("min_expense_ratio", "max_expense_ratio"),
            ("min_nav_usd", "max_nav_usd"),
            ("min_initial_investment_usd", "max_initial_investment_usd"),
            ("inception_date_from", "inception_date_to"),
            ("nav_as_of_from", "nav_as_of_to"),
        )
        for lo_name, hi_name in pairs:
            lo, hi = getattr(self, lo_name), getattr(self, hi_name)
            if lo is not None and hi is not None and lo > hi:
                raise ValueError(f"{lo_name} must be <= {hi_name}")
        return self


class GetMyHoldingsInput(StrictContract):
    """Empty by design; no user_id, account_number or arbitrary query."""


class GetMyAdvisorInput(StrictContract):
    """Empty by design; signed-in client comes from verified identity context."""


GetFundOutput = ToolResult[Fund]
GetFundReturnsOutput = ToolResult[FundReturns]
SearchFundsOutput = ToolResult[list[Fund]]
GetMyHoldingsOutput = ToolResult[list[Holding]]
GetMyAdvisorOutput = ToolResult[Advisor]
