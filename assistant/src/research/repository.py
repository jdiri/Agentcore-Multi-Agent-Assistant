
import boto3
from boto3.dynamodb.conditions import Key


class ResearchRepository:
    def __init__(self):
        dynamodb = boto3.resource("dynamodb")

        self.funds_table = dynamodb.Table("p3-funds")
        self.users_table = dynamodb.Table("p3-users")
        self.holdings_table = dynamodb.Table("p3-holdings")
        self.advisors_table = dynamodb.Table("p3-advisors")

    # 1. Get a fund by its ticker
    def get_fund(self, ticker: str) -> dict | None:
        response = self.funds_table.get_item(
            Key={"ticker": ticker}
        )

        return response.get("Item")

    # 2. Retrieve all funds
    def list_funds(self) -> list[dict]:
        items = []

        response = self.funds_table.scan()
        items.extend(response["Items"])

        # Handle DynamoDB pagination
        while "LastEvaluatedKey" in response:
            response = self.funds_table.scan(
                ExclusiveStartKey=response["LastEvaluatedKey"]
            )
            items.extend(response["Items"])

        return items

    # 3. Get a user by ID
    def get_user(self, user_id: str) -> dict | None:
        response = self.users_table.get_item(
            Key={"user_id": user_id}
        )

        return response.get("Item")

    # 4. Get all holdings belonging to a user
    def get_holdings_by_user(self, user_id: str) -> list[dict]:
        items = []

        response = self.holdings_table.query(
            KeyConditionExpression=Key("user_id").eq(user_id)
        )

        items.extend(response["Items"])

        while "LastEvaluatedKey" in response:
            response = self.holdings_table.query(
                KeyConditionExpression=Key("user_id").eq(user_id),
                ExclusiveStartKey=response["LastEvaluatedKey"]
            )
            items.extend(response["Items"])

        return items

    # 5. Get an advisor by ID
    def get_advisor(self, advisor_id: str) -> dict | None:
        response = self.advisors_table.get_item(
            Key={"advisor_id": advisor_id}
        )

        return response.get("Item")
