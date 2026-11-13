"""AgentCore Gateway -> Lambda adapter (first tool: get_fund).

Requires research_tools.py, research_service.py and research_repository.py
from the application's service/repository implementation.
"""
import logging

from pydantic import ValidationError

from research.repository import ResearchRepository
from research.service import ResearchService
from tools.research_tools import ResearchTools

logger = logging.getLogger(__name__)
_tools = None


def get_tools():
    global _tools
    if _tools is None:
        _tools = ResearchTools(ResearchService(ResearchRepository()))
    return _tools


def lambda_handler(event, context):
    # This metadata comes from AgentCore Gateway's Lambda invocation context.
    client_context = getattr(context, "client_context", None)
    metadata = getattr(client_context, "custom", None) or {}
    full_name = metadata.get("bedrockAgentCoreToolName", "")
    tool_name = full_name.rsplit("___", 1)[-1] if "___" in full_name else ""

    if tool_name != "get_fund":
        return {"error": "Unsupported tool"}

    if not isinstance(event, dict):
        return {"error": "Invalid tool arguments"}

    try:
        # Pydantic contract rejects unexpected arguments, including user_id.
        from common.contracts.research import GetFundInput
        request = GetFundInput.model_validate(event)
        return get_tools().get_fund(ticker=request.ticker)
    except ValidationError:
        return {"error": "Invalid tool arguments"}
    except Exception:
        logger.exception("Research get_fund failed")
        return {"error": "Research tool temporarily unavailable"}
