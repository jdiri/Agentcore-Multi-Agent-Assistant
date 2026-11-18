"""AgentCore Runtime #1 entrypoint.

Set `P3_STUB_ROUTER=1` to run locally without AWS. Specialists are stubs until their config is
present: Support is real once `P3_KB_ID` is set.
"""

import logging
import os
import uuid
from functools import cache

from bedrock_agentcore.runtime import BedrockAgentCoreApp, RequestContext
from starlette.responses import JSONResponse

from common.contracts import Specialist
from coordinator.graph import build_coordinator
from coordinator.stubs import STUB_SPECIALISTS, stub_router

logger = logging.getLogger(__name__)

app = BedrockAgentCoreApp()


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
