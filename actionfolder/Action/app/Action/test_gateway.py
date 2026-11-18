
import asyncio
import httpx

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from gateway import gateway_url, SigV4HttpxAuth
from config import AWS_REGION


async def main():
    async with httpx.AsyncClient(
        timeout=60.0,
        auth=SigV4HttpxAuth(AWS_REGION),
        follow_redirects=True
    ) as http_client:

        async with streamable_http_client(
            gateway_url(),
            http_client=http_client
        ) as (read, write):

            async with ClientSession(read, write) as session:
                await session.initialize()

                result = await session.list_tools()

                print("\nAvailable Gateway Tools:")

                for tool in result.tools:
                    print(f"- {tool.name}")


if __name__ == "__main__":
    asyncio.run(main())
