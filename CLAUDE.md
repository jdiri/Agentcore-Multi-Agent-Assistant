# CLAUDE.md

Multi-agent client-service assistant for "Lanternfield", a fictional fund family, built on AWS
AgentCore with LangGraph. Team of four (workstreams A–D in `assistant/docs/roadmap.md`).

**All funds, people, accounts and policies in this project are synthetic.** Never present them
as real financial data, and never give investment advice in code, prompts or tests.

## Where things are

All code lives under `assistant/`. Run every command from there unless noted.

- `src/coordinator/`: Runtime #1. `graph.py` (route → run_specialist → compose), `router.py`
  (Bedrock structured routing), `runtime.py` (AgentCore entrypoint), `stubs.py` (keyword router
  and stand-in specialists).
- `src/common/contracts/`: shared Pydantic v2 contracts. `routing.py` is the canonical
  Coordinator ↔ specialist contract (owner A). `research.py` (C), `support.py` (B),
  `identity.py`, `protocol.py` and `action.py` (D) build on it. All four workstreams depend on
  these, so change them deliberately and tell the owner.
- `src/support/`, `src/research/`, `src/action/`, `src/approval/`, `src/lifecycle/`,
  `src/tools/`: specialist and tool packages, mostly empty until each track fills them in.
- `tests/unit/`: pytest. `tests/integration/` and `tests/e2e/` need AWS.
- `p3coordinator/`: AgentCore CLI project for Runtime #1. `app/coordinator/main.py` only imports
  from `src/coordinator`. Its `AGENTS.md` has the CLI's own rules; follow them there.
- `Project3-Corpus-Documents/p3-corpus/`: the 18 KB documents, JSON data and ground-truth evals.
  Source data only. Never edit it.
- `docs/project-blueprint.md` is the brief. `docs/roadmap.md` is the plan, decisions D1–D9 and
  the acceptance checklist. Read the relevant section before designing anything new.

## Architecture rules (from the brief; do not break)

- The Coordinator has no business tools. It writes replies only from specialist reports.
- Routing can only target the `Specialist` enum. Limits: at most 4 hand-offs per turn, no
  specialist twice without a `repeat_justification`, at most 3 tool rounds per specialist,
  max tokens 1,024 for the Coordinator and 2,048 for specialists.
- Specialists receive only their `SpecialistTask`, never the shared conversation, and return a
  `SpecialistReport`. Every claim in a reply must come from a report finding.
- Tool names are fixed: `get_fund`, `get_fund_returns`, `search_funds`, `get_my_holdings`,
  `get_my_advisor`, `draft_email`, `send_approved_email`, `create_ticket`. Tools take no
  client-ID argument and no open-ended query. `user_id` comes only from the verified identity
  context, never from model-visible fields.
- Only Action writes. It runs in Runtime #2, reached over authenticated A2A. Emails need an
  `APPROVED` request, and the send path re-reads stored state before sending.
- Lifecycle: `DRAFTED → PENDING_APPROVAL → APPROVED → EXECUTED`, with `DECLINED`, `EXPIRED`,
  `FAILED` as exits. Only code changes state. Every change is audited. Illegal transitions are
  refused and logged.
- Support answers only from the Knowledge Base, cites as
  `Sources: [Account Transfer Policy v3.2, s.4] [Fee Schedule FAQ, 2026-01]`, never cites a
  superseded version, and below the relevance threshold replies exactly:
  "I don't have that information in my documents. Would you like me to open a ticket?"
- Tool failures are reported, never filled in with invented data.
- Never log raw client text, account numbers or SSN-like strings. Log IDs and error types only.

## How to work

- Python 3.11+, Pydantic v2, LangGraph, `langchain-aws` (`ChatBedrockConverse`). Any graph node
  that calls a tool must be `async`.
- Contracts are frozen with `extra="forbid"`. Match the style in `contracts/routing.py`.
- Stub mode must keep working without AWS access: `P3_STUB_ROUTER=1 python src/coordinator/runtime.py`.
- Make small, focused changes. Add or update unit tests in `tests/unit` with every change.
- Before calling a change done, run from `assistant/` and report failures honestly:
  ```
  pytest tests/unit
  ruff check .
  ruff format --check .
  ```
  CI runs the same on Python 3.11 and 3.14. Line length is 100.
- If a request conflicts with the brief or with another workstream's contract, say so before
  writing code.
- Commit or push only when asked. Never commit AWS keys, account IDs, ARNs, `.env` files,
  `aws-targets.json` or `agentcore/.cli/`. The gitleaks pre-commit hook catches keys, not
  account IDs, so check by hand.
