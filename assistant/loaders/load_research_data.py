
import json
from decimal import Decimal
from pathlib import Path

import boto3

from common.contracts.research import Fund


DATA_DIR = (
    Path(__file__).resolve().parents[1]
    / "Project3-Corpus-Documents"
    / "p3-corpus"
    / "data"
)

TABLE_FILES = {
    "p3-funds": "funds.json",
    "p3-users": "users.json",
    "p3-holdings": "holdings.json",
    "p3-advisors": "advisors.json",
}


def load_json(filename: str) -> list[dict]:
    path = DATA_DIR / filename

    with path.open(encoding="utf-8") as file:
        return json.load(file, parse_float=Decimal)


def prepare_item(table_name: str, record: dict) -> dict:
    item = record.copy()

    if table_name == "p3-funds":
        # Validate using the existing shared contract.
        Fund.model_validate(item)

    if table_name == "p3-holdings":
        item["holding_key"] = (
            f"{item['account_number']}#{item['ticker']}"
        )

    return item


def load_data():
    dynamodb = boto3.resource("dynamodb")

    for table_name, filename in TABLE_FILES.items():
        table = dynamodb.Table(table_name)
        records = load_json(filename)

        with table.batch_writer() as batch:
            for record in records:
                item = prepare_item(table_name, record)
                batch.put_item(Item=item)

        print(f"Loaded {len(records)} records into {table_name}")


if __name__ == "__main__":
    load_data()
