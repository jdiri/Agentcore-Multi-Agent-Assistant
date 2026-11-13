"""Local demo: the Coordinator with the real Support agent; the other specialists are stubs.

Run from assistant/ with AWS credentials configured and P3_KB_ID set:
    python scripts/demo.py                       # Q01 (cited answer), then Q25 (gap reply)
    python scripts/demo.py "How do I close my account?"
    python scripts/demo.py --bedrock-router      # Track A's Bedrock router instead

By default every question goes to Support, so the demo shows Track B and needs no routing model.
Track A's files are not changed: the Support handler is swapped in here, not in stubs.py.
"""

import argparse
import asyncio
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from common.contracts import (  # noqa: E402
    Delegation,
    RoutingDecision,
    Specialist,
)
from coordinator.graph import build_coordinator  # noqa: E402
from coordinator.stubs import STUB_SPECIALISTS  # noqa: E402

DEMO_QUESTIONS = (
    (
        "Q01: policy question, expect a v3.2 citation",
        "How long does an incoming ACATS transfer take?",
    ),
    (
        "Q25: gap question, expect the gap reply",
        "How do I add or change the beneficiary on my IRA?",
    ),
)


async def support_router(message: str) -> RoutingDecision:
    """Send every question to Support."""
    return RoutingDecision(delegations=[Delegation(specialist=Specialist.SUPPORT, task=message)])


def build_demo_coordinator(support_handler, route=support_router):
    return build_coordinator(route, {**STUB_SPECIALISTS, Specialist.SUPPORT: support_handler})


async def ask(coordinator, question: str) -> str:
    result = await coordinator.ainvoke(
        {"message": question, "session_id": "demo", "turn_id": str(uuid.uuid4())}
    )
    return result["reply"]


async def main_async(questions, *, bedrock_router: bool) -> None:
    from support.agent import create_support_handler

    route = support_router
    if bedrock_router:
        from coordinator.router import create_bedrock_router

        route = create_bedrock_router()
    coordinator = build_demo_coordinator(create_support_handler(), route)
    for label, question in questions:
        print(f"=== {label}\nClient: {question}\n")
        print(f"Assistant: {await ask(coordinator, question)}\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Lanternfield Support demo (synthetic data).")
    parser.add_argument("question", nargs="*", help="ask this instead of Q01 and Q25")
    parser.add_argument("--bedrock-router", action="store_true", help="use Track A's router")
    args = parser.parse_args()
    questions = [("Your question", " ".join(args.question))] if args.question else DEMO_QUESTIONS
    asyncio.run(main_async(questions, bedrock_router=args.bedrock_router))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
