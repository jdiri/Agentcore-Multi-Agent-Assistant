"""Run the routing eval (R01-R46) against the real Bedrock router and write a report.

Needs AWS credentials with Bedrock access. Run from `assistant/`:

    python evals/routing/run_routing.py                  # 3 runs, default model
    python evals/routing/run_routing.py --runs 1 --model amazon.nova-pro-v1:0

The report goes to `docs/results/routing-YYYYMMDD-N.md`.
"""

import argparse
import asyncio
import os
from datetime import date
from pathlib import Path

from coordinator.router import DEFAULT_MODEL_ID, create_bedrock_router
from coordinator.routing_eval import load_cases, render_report, run_cases

ASSISTANT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_CASES = ASSISTANT_DIR / "Project3-Corpus-Documents/p3-corpus/ground-truth/routing.jsonl"
DEFAULT_OUT = ASSISTANT_DIR / "docs/results"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--model", default=os.environ.get("COORDINATOR_MODEL_ID", DEFAULT_MODEL_ID))
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--concurrency", type=int, default=4)
    return parser.parse_args()


def next_report_path(out_dir: Path, today: date) -> Path:
    stem = f"routing-{today:%Y%m%d}"
    number = 1
    while (out_dir / f"{stem}-{number}.md").exists():
        number += 1
    return out_dir / f"{stem}-{number}.md"


async def main() -> None:
    args = parse_args()
    cases = load_cases(args.cases)
    route = create_bedrock_router(args.model)

    runs = []
    for number in range(1, args.runs + 1):
        results = await run_cases(route, cases, args.concurrency)
        runs.append(results)
        passed = sum(result.passed for result in results)
        errors = sum(result.error is not None for result in results)
        print(f"run {number}: {passed}/{len(cases)} passed ({errors} errors)")

    today = date.today()
    args.out.mkdir(parents=True, exist_ok=True)
    path = next_report_path(args.out, today)
    path.write_text(render_report(args.model, runs, cases, today), encoding="utf-8")
    print(f"report: {path}")


if __name__ == "__main__":
    asyncio.run(main())
