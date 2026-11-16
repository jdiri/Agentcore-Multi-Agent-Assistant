"""Shared Bedrock client settings: bounded retries on throttling, and timeouts.

Pass `config=bedrock_client_config()` to `ChatBedrockConverse`. botocore's "standard" retry mode
backs off and retries throttling and transient errors, so callers should not add their own retry
loop around those errors (the attempts would multiply).
"""

import asyncio

from botocore.config import Config
from botocore.exceptions import ClientError, ConnectTimeoutError, ReadTimeoutError

MAX_ATTEMPTS = 3  # the first call plus two retries
CONNECT_TIMEOUT_SECONDS = 5
READ_TIMEOUT_SECONDS = 30

BUSY_ERROR_CODES = frozenset(
    {
        "ThrottlingException",
        "TooManyRequestsException",
        "ServiceUnavailableException",
        "ModelNotReadyException",
        "ModelTimeoutException",
    }
)


def bedrock_client_config() -> Config:
    return Config(
        retries={"max_attempts": MAX_ATTEMPTS, "mode": "standard"},
        connect_timeout=CONNECT_TIMEOUT_SECONDS,
        read_timeout=READ_TIMEOUT_SECONDS,
    )


def is_busy_error(exc: BaseException) -> bool:
    """True for throttling and timeouts, which the client should hear as "busy, try again"."""
    if isinstance(exc, ClientError):
        return exc.response.get("Error", {}).get("Code") in BUSY_ERROR_CODES
    return isinstance(exc, ReadTimeoutError | ConnectTimeoutError | asyncio.TimeoutError)
