"""AgentCore Runtime #1 entrypoint.

Set `P3_STUB_ROUTER=1` to run locally without AWS. Specialists are stubs until each owner
replaces their entry in `coordinator.stubs.STUB_SPECIALISTS`.
"""

import os
import uuid
from functools import cache

from bedrock_agentcore.runtime import BedrockAgentCoreApp, RequestContext
from starlette.responses import JSONResponse

from coordinator.graph import build_coordinator
from coordinator.stubs import STUB_SPECIALISTS, stub_router

app = BedrockAgentCoreApp()


@cache
def get_coordinator():
    if os.environ.get("P3_STUB_ROUTER") == "1":
        route = stub_router
    else:
        # Imported here so stub mode needs no Bedrock client or region.
        from coordinator.router import create_bedrock_router

        route = create_bedrock_router()
    return build_coordinator(route, STUB_SPECIALISTS)


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
