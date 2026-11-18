import json
from decimal import Decimal

from common.contracts.base import ToolStatus
from common.contracts.research import (
    Fund,
    SearchFundsInput,
    SearchFundsOutput,
)
from tools.get_fund_local import FUNDS_FILE


def search_funds_local(
    request: SearchFundsInput,
) -> SearchFundsOutput:

    with FUNDS_FILE.open(encoding="utf-8") as file:
        records = json.load(file, parse_float=Decimal)

    funds = [Fund.model_validate(record) for record in records]

    filters = request.model_dump(exclude_none=True)

    field_mapping = {
        "max_expense_ratio": ("expense_ratio_pct", "max"),
        "min_expense_ratio": ("expense_ratio_pct", "min"),
        "min_nav_usd": ("nav_usd", "min"),
        "max_nav_usd": ("nav_usd", "max"),
        "min_initial_investment_usd": (
            "minimum_initial_investment_usd", "min"
        ),
        "max_initial_investment_usd": (
            "minimum_initial_investment_usd", "max"
        ),
        "inception_date_from": ("inception_date", "min"),
        "inception_date_to": ("inception_date", "max"),
        "nav_as_of_from": ("nav_as_of", "min"),
        "nav_as_of_to": ("nav_as_of", "max"),
    }

    def matches(fund: Fund) -> bool:
        for key, value in filters.items():

            if key == "name_contains":
                if value.casefold() not in fund.name.casefold():
                    return False

            elif key in ("asset_class", "management"):
                if getattr(fund, key) != value:
                    return False

            else:
                field, direction = field_mapping[key]
                actual = getattr(fund, field)

                if direction == "min" and actual < value:
                    return False

                if direction == "max" and actual > value:
                    return False

        return True

    matching_funds = [fund for fund in funds if matches(fund)]

    return SearchFundsOutput(
        status=ToolStatus.OK,
        data=matching_funds,
    )