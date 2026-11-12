"""Score the Coordinator's routing against the labeled cases in `ground-truth/routing.jsonl`.

Pure code with no AWS calls: `evals/routing/run_routing.py` supplies the real router.

Scoring rules (from the corpus README):
- `expected` is the ordered list of delegations. An empty list means a refusal, and `refusal`
  names the reason.
- `also_acceptable` lists other correct delegation lists. An empty one with no reason given
  means any refusal is fine.
- A router error counts as a failure and is recorded by error type only.
"""

import asyncio
import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from common.contracts import RefusalReason, RoutingDecision, Specialist
from coordinator.graph import Router

Route = tuple[Specialist, ...]

CATEGORIES = ("single", "multi", "refusal")


@dataclass(frozen=True)
class RoutingCase:
    id: str
    message: str
    expected: Route
    refusal: RefusalReason | None = None
    also_acceptable: tuple[Route, ...] = ()

    @property
    def category(self) -> str:
        if not self.expected:
            return "refusal"
        return "single" if len(self.expected) == 1 else "multi"


@dataclass(frozen=True)
class CaseResult:
    case_id: str
    passed: bool
    got_route: Route = ()
    got_refusal: RefusalReason | None = None
    error: str | None = None

    def describe(self) -> str:
        if self.error:
            return f"error: {self.error}"
        if self.got_refusal:
            return f"refusal: {self.got_refusal}"
        return " → ".join(self.got_route) or "(nothing)"


def load_cases(path: Path) -> list[RoutingCase]:
    """Read the JSONL file. Unknown specialists or refusal reasons raise ValueError."""
    cases = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        cases.append(
            RoutingCase(
                id=row["id"],
                message=row["message"],
                expected=_route(row["expected"]),
                refusal=RefusalReason(row["refusal"]) if row.get("refusal") else None,
                also_acceptable=tuple(_route(alt) for alt in row.get("also_acceptable", ())),
            )
        )
    return cases


def _route(names: Iterable[str]) -> Route:
    return tuple(Specialist(name) for name in names)


def score_case(
    case: RoutingCase, decision: RoutingDecision | None, error: str | None = None
) -> CaseResult:
    if decision is None:
        return CaseResult(case.id, passed=False, error=error or "no decision")

    got_route = tuple(delegation.specialist for delegation in decision.delegations)
    got_refusal = decision.refusal
    if got_refusal is not None:
        # Any empty acceptable list allows a refusal; only the primary one names the reason.
        passed = (not case.expected and got_refusal == case.refusal) or any(
            not alt for alt in case.also_acceptable
        )
    else:
        passed = bool(got_route) and (
            got_route == case.expected or got_route in case.also_acceptable
        )
    return CaseResult(case.id, passed=passed, got_route=got_route, got_refusal=got_refusal)


async def run_cases(
    route: Router, cases: Sequence[RoutingCase], concurrency: int = 4
) -> list[CaseResult]:
    """Route every case, at most `concurrency` at a time. Errors never escape."""
    limit = asyncio.Semaphore(concurrency)

    async def one(case: RoutingCase) -> CaseResult:
        async with limit:
            try:
                decision = await route(case.message)
            except Exception as exc:
                return score_case(case, None, type(exc).__name__)
        return score_case(case, decision)

    return list(await asyncio.gather(*(one(case) for case in cases)))


def render_report(
    model_id: str,
    runs: Sequence[Sequence[CaseResult]],
    cases: Sequence[RoutingCase],
    run_date: date | None = None,
) -> str:
    """Markdown report: score per run, per category, per case, then the failures."""
    total = len(cases)
    by_category = {name: [c.id for c in cases if c.category == name] for name in CATEGORIES}
    category_headers = " | ".join(f"{name} ({len(ids)})" for name, ids in by_category.items())
    lines = [
        "# Routing eval",
        "",
        f"- Date: {(run_date or date.today()).isoformat()}",
        f"- Model: `{model_id}`",
        f"- Cases: {total} (`ground-truth/routing.jsonl`), runs: {len(runs)}",
        "",
        "## Score per run",
        "",
        f"| Run | Total | {category_headers} |",
        "|---|---|" + "---|" * len(by_category),
    ]
    for number, results in enumerate(runs, start=1):
        passed = {r.case_id for r in results if r.passed}
        per_category = " | ".join(
            str(sum(case_id in passed for case_id in ids)) for ids in by_category.values()
        )
        lines.append(f"| {number} | **{len(passed)}/{total}** | {per_category} |")

    results_by_case = {case.id: [run_by_id(run)[case.id] for run in runs] for case in cases}
    lines += [
        "",
        "## Per case",
        "",
        "| Case | Category | Expected | Passed | Got (failed runs) |",
        "|---|---|---|---|---|",
    ]
    failed_any = []
    for case in cases:
        results = results_by_case[case.id]
        passes = sum(r.passed for r in results)
        failures = sorted({r.describe() for r in results if not r.passed})
        if failures:
            failed_any.append(case)
        lines.append(
            f"| {case.id} | {case.category} | {_expected(case)} | {passes}/{len(results)} "
            f"| {'; '.join(failures)} |"
        )

    lines += ["", "## Failed in any run", ""]
    if failed_any:
        lines += [f"- **{case.id}** ({_expected(case)}): {case.message}" for case in failed_any]
    else:
        lines.append("None.")
    return "\n".join(lines) + "\n"


def run_by_id(results: Iterable[CaseResult]) -> dict[str, CaseResult]:
    return {result.case_id: result for result in results}


def _expected(case: RoutingCase) -> str:
    if not case.expected:
        return f"refusal: {case.refusal}"
    text = " → ".join(case.expected)
    if case.also_acceptable:
        alts = ", ".join(" → ".join(alt) or "refusal" for alt in case.also_acceptable)
        text += f" (or {alts})"
    return text
