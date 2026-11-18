
import logging

from pydantic import ValidationError

from common.contracts.research import (
    GetFundInput,
    GetFundReturnsInput,
    SearchFundsInput,
)

from research.repository import ResearchRepository
from research.service import ResearchService
from tools.research_tools import ResearchTools


logger = logging.getLogger(__name__)

_tools = None


def get_tools() -> ResearchTools:
    """Initialize the backend once per warm Lambda environment."""
    global _tools

    if _tools is None:
        repository = ResearchRepository()
        service = ResearchService(repository)
        _tools = ResearchTools(service)

    return _tools


def lambda_handler(event, context):
    """Dispatch AgentCore Gateway tool calls."""

    # 1. Identify the requested Gateway tool.
    client_context = getattr(context, "client_context", None)
    metadata = getattr(client_context, "custom", None) or {}

    full_name = metadata.get("bedrockAgentCoreToolName", "")

    if "___" not in full_name:
        return {
            "error": "Missing or invalid Gateway tool name"
        }

    tool_name = full_name.rsplit("___", 1)[-1]

    # 2. Explicitly allow only the catalog tools.
    allowed_tools = {
        "get_fund",
        "get_fund_returns",
        "search_funds",
    }

    if tool_name not in allowed_tools:
        return {
            "error": "Unsupported tool"
        }

    # 3. Check input format.
    if not isinstance(event, dict):
        return {
            "error": "Invalid tool arguments"
        }

    try:
        # 4. Validate and dispatch the request.
        if tool_name == "get_fund":
            request = GetFundInput.model_validate(event)

            return get_tools().get_fund(
                ticker=request.ticker
            )

        if tool_name == "get_fund_returns":
            request = GetFundReturnsInput.model_validate(event)

            return get_tools().get_fund_returns(
                ticker=request.ticker,
                quarters=request.quarters,
            )

        if tool_name == "search_funds":
            request = SearchFundsInput.model_validate(event)

            return get_tools().search_funds(
                **request.model_dump(exclude_none=True)
            )

    except ValidationError:
        logger.warning(
            "Invalid arguments for tool %s",
            tool_name,
        )
        return {
            "error": "Invalid tool arguments"
        }

    except Exception:
        logger.exception(
            "Research tool failed: %s",
            tool_name,
        )
        return {
            "error": "Research tool temporarily unavailable"
        }
