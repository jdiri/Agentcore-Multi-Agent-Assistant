
import os
import json
import boto3
import httpx

from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from mcp.client.streamable_http import streamable_http_client
from mcp import ClientSession

from config import AWS_REGION


SIGNING_SERVICE = "bedrock-agentcore"
UNSIGNABLE = {"connection", "host", "content-length"}
TIMEOUT_SECONDS = 60.0


class SigV4HttpxAuth(httpx.Auth):
    """Sign outbound HTTP requests using AWS SigV4."""

    requires_request_body = True

    def __init__(self, region: str) -> None:
        credentials = boto3.Session().get_credentials()

        if credentials is None:
            raise RuntimeError(
                "No AWS credentials. Locally, set AWS_PROFILE. "
                "Deployed, check the runtime execution role."
            )

        self._signer = SigV4Auth(
            credentials,
            SIGNING_SERVICE,
            region
        )

    def auth_flow(self, request: httpx.Request):
        aws_request = AWSRequest(
            method=request.method,
            url=str(request.url),
            data=request.content or "",
            headers={
                key: value
                for key, value in request.headers.items()
                if key.lower() not in UNSIGNABLE
            }
        )

        self._signer.add_auth(aws_request)

        for key, value in aws_request.headers.items():
            request.headers[key] = value

        yield request


def gateway_url() -> str:
    """Get the Gateway URL injected by the AgentCore CLI."""

    for key, value in os.environ.items():
        if key.startswith("AGENTCORE_GATEWAY_") and key.endswith("_URL"):
            return value

    raise RuntimeError("AgentCore Gateway URL was not found in environment variables.")


async def call_gateway_tool(tool_name: str, arguments: dict) -> dict:
    """Connect to AgentCore Gateway and invoke a specific MCP tool."""

    url = gateway_url()

    async with httpx.AsyncClient(
        timeout=TIMEOUT_SECONDS,
        auth=SigV4HttpxAuth(AWS_REGION),
        follow_redirects=True
    ) as http_client:

        async with streamable_http_client(
            url,
            http_client=http_client
        ) as (read, write, _):

            async with ClientSession(read, write) as session:
                await session.initialize()

                result = await session.call_tool(
                    tool_name,
                    arguments=arguments
                )

                if result.isError:
                    raise RuntimeError(
                        f"Gateway tool '{tool_name}' failed: {result.content}"
                    )


                return result.structuredContent
