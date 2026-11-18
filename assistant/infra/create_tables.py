
import boto3
from botocore.exceptions import ClientError


TABLES = {
    # Research tables
    "p3-funds": {
        "keys": ["ticker"],
    },
    "p3-users": {
        "keys": ["user_id"],
    },
    "p3-holdings": {
        "keys": ["user_id", "holding_key"],
    },
    "p3-advisors": {
        "keys": ["advisor_id"],
    },

    # Action tables
    "p3-action-requests": {
        "keys": ["request_id"],
        "indexes": {
            "user-requests-index": ["user_id", "created_at"],
        },
    },
    "p3-audit-log": {
        "keys": ["request_id", "event_key"],
    },
    "p3-tickets": {
        "keys": ["ticket_number"],
        "indexes": {
            "user-tickets-index": ["user_id", "created_at"],
        },
    },
    "p3-approval-tokens": {
        "keys": ["token_hash"],
        "ttl": "expires_at",
    },
}


def create_tables():
    dynamodb = boto3.resource("dynamodb")
    client = dynamodb.meta.client

    for table_name, config in TABLES.items():
        keys = config["keys"]
        indexes = config.get("indexes", {})

        key_schema = [
            {"AttributeName": keys[0], "KeyType": "HASH"}
        ]

        if len(keys) == 2:
            key_schema.append({
                "AttributeName": keys[1],
                "KeyType": "RANGE",
            })

        # DynamoDB only needs attribute definitions
        # for primary keys and index keys.
        attributes = {
            key: "S" for key in keys
        }

        global_indexes = []

        for index_name, index_keys in indexes.items():
            index_schema = [
                {
                    "AttributeName": index_keys[0],
                    "KeyType": "HASH",
                }
            ]

            if len(index_keys) == 2:
                index_schema.append({
                    "AttributeName": index_keys[1],
                    "KeyType": "RANGE",
                })

            for key in index_keys:
                attributes[key] = "S"

            global_indexes.append({
                "IndexName": index_name,
                "KeySchema": index_schema,
                "Projection": {
                    "ProjectionType": "ALL",
                },
            })

        attribute_definitions = [
            {
                "AttributeName": name,
                "AttributeType": attr_type,
            }
            for name, attr_type in attributes.items()
        ]

        params = {
            "TableName": table_name,
            "KeySchema": key_schema,
            "AttributeDefinitions": attribute_definitions,
            "BillingMode": "PAY_PER_REQUEST",
        }

        if global_indexes:
            params["GlobalSecondaryIndexes"] = global_indexes

        try:
            table = dynamodb.create_table(**params)

            print(f"Creating {table_name}...")
            table.wait_until_exists()
            print(f"{table_name} is ready")

        except ClientError as error:
            code = error.response["Error"]["Code"]

            if code == "ResourceInUseException":
                existing = dynamodb.Table(table_name)
                existing.load()

                actual_keys = existing.key_schema

                if actual_keys != key_schema:
                    raise RuntimeError(
                        f"{table_name} exists with a different key schema"
                    ) from error

                # Existing indexes must also match.
                actual_indexes = {
                    index["IndexName"]: index["KeySchema"]
                    for index in existing.global_secondary_indexes or []
                }

                expected_indexes = {
                    index["IndexName"]: index["KeySchema"]
                    for index in global_indexes
                }

                if actual_indexes != expected_indexes:
                    raise RuntimeError(
                        f"{table_name} exists with different indexes"
                    ) from error

                print(f"{table_name} already exists")

            else:
                raise

        # TTL is configured separately from CreateTable.
        if "ttl" in config:
            ttl_attribute = config["ttl"]

            ttl = client.describe_time_to_live(
                TableName=table_name
            )["TimeToLiveDescription"]

            status = ttl.get("TimeToLiveStatus")
            current_attribute = ttl.get("AttributeName")

            if status == "DISABLED":
                client.update_time_to_live(
                    TableName=table_name,
                    TimeToLiveSpecification={
                        "Enabled": True,
                        "AttributeName": ttl_attribute,
                    },
                )
                print(f"Enabling TTL on {table_name}")

            elif current_attribute != ttl_attribute:
                raise RuntimeError(
                    f"{table_name} has an unexpected TTL attribute"
                )

            else:
                print(f"TTL already configured on {table_name}")


if __name__ == "__main__":
    create_tables()
