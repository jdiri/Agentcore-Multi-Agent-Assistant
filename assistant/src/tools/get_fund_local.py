import json
from decimal import Decimal
from pathlib import Path

from common.contracts.base import ToolStatus
from common.contracts.research import (
    Fund,
    GetFundInput,
    GetFundOutput,
)

FUNDS_FILE = (
    Path(__file__).resolve().parents[2] / "Project3-Corpus-Documents/p3-corpus/data/funds.json"
)


def get_fund_local(request: GetFundInput) -> GetFundOutput:
    with FUNDS_FILE.open(encoding="utf-8") as file:
        funds = json.load(file, parse_float=Decimal)

    for record in funds:
        if record["ticker"] == request.ticker:
            return GetFundOutput(
                status=ToolStatus.OK,
                data=Fund.model_validate(record),
            )

    return GetFundOutput(status=ToolStatus.NOT_FOUND)
