from decimal import Decimal

import pytest
from pydantic import ValidationError

from common.contracts.base import ToolStatus
from common.contracts.research import SearchFundsInput
from tools.search_funds_local import search_funds_local


def test_search_index_funds():
    result = search_funds_local(
        SearchFundsInput(management="Index")
    )

    assert result.status == ToolStatus.OK
    assert len(result.data) > 0
    assert all(fund.management == "Index" for fund in result.data)


def test_search_multiple_filters():
    result = search_funds_local(
        SearchFundsInput(
            management="Index",
            max_expense_ratio=Decimal("0.10"),
        )
    )

    assert result.status == ToolStatus.OK

    for fund in result.data:
        assert fund.management == "Index"
        assert fund.expense_ratio_pct <= Decimal("0.10")


def test_search_no_matches():
    result = search_funds_local(
        SearchFundsInput(name_contains="NONEXISTENT FUND")
    )

    assert result.status == ToolStatus.OK
    assert result.data == []


def test_search_requires_filter():
    with pytest.raises(ValidationError):
        SearchFundsInput()


def test_invalid_filter_range():
    with pytest.raises(ValidationError):
        SearchFundsInput(
            min_nav_usd=Decimal("200"),
            max_nav_usd=Decimal("100"),
        )