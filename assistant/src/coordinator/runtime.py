"""AgentCore Runtime #1 entrypoint.

Set `P3_STUB_ROUTER=1` to run locally without AWS. Specialists are stubs until their config is
present: Support is real once `P3_KB_ID` is set.
"""

import logging
import os
import uuid
from functools import cache

from bedrock_agentcore.runtime import BedrockAgentCoreApp, RequestContext
from bedrock_agentcore.runtime.app import RequestContextFormatter
from starlette.responses import JSONResponse

from common.contracts import Specialist
from common.masking import MaskingFilter
from coordinator.graph import build_coordinator
from coordinator.stubs import STUB_SPECIALISTS, stub_router

# Named explicitly: run as a script (stub mode) __name__ is "__main__", outside APP_LOGGERS.
logger = logging.getLogger("coordinator.runtime")

# Our packages log at INFO (Support's gap log is INFO). Libraries keep the WARNING default.
APP_LOGGERS = ("coordinator", "support", "common")
AGENTCORE_LOGGER = "bedrock_agentcore.app"
_HANDLER_NAME = "p3-masked-json"


def configure_logging() -> None:
    """Send our logs to stdout (CloudWatch in the runtime) as JSON, masked. Safe to call twice.

    One root handler with AgentCore's JSON formatter (adds requestId and sessionId) and
    `MaskingFilter`, so every line from our packages is masked even if a caller forgets.
    AgentCore's own logger has its own handler: it gets the filter too, and stops propagating
    so its lines are not written twice. Masking covers the message, not exception text, so
    keep logging error types only.
    """
    root = logging.getLogger()
    if not any(h.get_name() == _HANDLER_NAME for h in root.handlers):
        handler = logging.StreamHandler()
        handler.set_name(_HANDLER_NAME)
        handler.setFormatter(RequestContextFormatter())
        handler.addFilter(MaskingFilter())
        root.addHandler(handler)
    for name in APP_LOGGERS:
        logging.getLogger(name).setLevel(logging.INFO)
    agentcore = logging.getLogger(AGENTCORE_LOGGER)
    agentcore.propagate = False
    for handler in agentcore.handlers:
        if not any(isinstance(f, MaskingFilter) for f in handler.filters):
            handler.addFilter(MaskingFilter())


app = BedrockAgentCoreApp()
configure_logging()


def _specialists():
    """Stubs, with each real specialist swapped in once its config is present."""
    specialists = dict(STUB_SPECIALISTS)
    if os.environ.get("P3_KB_ID"):
        # Imported here so stub mode needs no Bedrock client.
        from support.agent import create_support_handler

        specialists[Specialist.SUPPORT] = create_support_handler()
        logger.info("support handler: knowledge base")
    else:
        logger.info("support handler: stub")
    return specialists


@cache
def get_coordinator():
    if os.environ.get("P3_STUB_ROUTER") == "1":
        route = stub_router
    else:
        # Imported here so stub mode needs no Bedrock client or region.
        from coordinator.router import create_bedrock_router

        route = create_bedrock_router()
    return build_coordinator(route, _specialists())


@app.entrypoint
async def invoke(payload: dict, context: RequestContext):
    prompt = payload.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        return JSONResponse({"error": "prompt must be a non-empty string"}, status_code=400)

    session_id = context.session_id or str(uuid.uuid4())
    turn_id = str(uuid.uuid4())
    result = await get_coordinator().ainvoke(
        {"message": prompt, "session_id": session_id, "turn_id": turn_id}
    )
    decision = result.get("decision")
    return {
        "reply": result["reply"],
        "session_id": session_id,
        "turn_id": turn_id,
        "route": [d.specialist.value for d in decision.delegations] if decision else [],
        "refusal": decision.refusal.value if decision and decision.refusal else None,
    }


if __name__ == "__main__":
    app.run()
