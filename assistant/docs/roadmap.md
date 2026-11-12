# Project 3 Roadmap: Multi-Agent Financial Assistant on AWS AgentCore

> Sources: `docs/project-blueprint.md` (the brief) and `Project3-Corpus-Documents/p3-corpus/README.md` (data package).
> `§` references point to brief sections. All data is synthetic and must stay labeled that way.
> Team of 4. Placeholder names **Dev A–D**; replace with real names once workstreams are picked.

---

## 1. The project in one paragraph

Build a client-service assistant for the fictional "Lanternfield" fund family. A **Coordinator** (no tools) routes each part of a request to one of three specialists: **Support** (answers only from the Knowledge Base, with citations), **Research** (read-only fund and own-holdings data) and **Action** (the only writer: tickets and advisor emails). Action runs in its **own AgentCore Runtime, reached over authenticated A2A**. Every consequential tool sits behind **AgentCore Gateway with Cedar policies**. Emails need a **human approval by SES email link** that can't be replayed, tampered with or used late. All of this has to be **proven** with automated tests, AgentCore Evaluations (3+ runs), traces, measured latency and measured cost.

**Grading:** 5 × 20 pts (Architecture, Functional, Non-Functional, Presentation, Development). Everyone owning and presenting a real feature helps Presentation. A visible structured process helps Development.

---

## 2. Team & workstreams

Each person owns one end-to-end feature, works hands-on with several AgentCore services, owns one eval suite, and presents one demo segment.

| Dev | Workstream | Key features owned | AgentCore hands-on | Eval suite owned | Demo segment |
|---|---|---|---|---|---|
| **A** | **Orchestration & Memory** | Coordinator agent, routing enum validation, hand-off / tool-round limits, per-conversation tool-call ceiling, token caps, Runtime #1 deploy, A2A *client*, Cognito sign-in, short + long-term memory, resilience (throttling, memory down, Action down), turn tracing + session linking | Runtime, Memory, Identity (inbound), Observability (traces) | Routing (46) + memory tests | Intro, architecture, routing & memory |
| **B** | **Knowledge & Safety** | Bedrock KB + vector store, chunking, KB metadata + superseded filter, relevance-threshold calibration, Support agent + citations, gap logging, Guardrails (denied topics, content filters, prompt attack), account/SSN masking, shared eval runner | Evaluations (runner + faithfulness), Observability (masking proof) | Support QA (25) + injection/honesty tests | Cited answer, gap question, injection ignored |
| **C** | **Data, Tools & Gateway** | DynamoDB design + loaders, S3 upload, Research agent, 5 read tools (`get_fund`, `get_fund_returns`, `search_funds`, `get_my_holdings`, `get_my_advisor`), Gateway targets, Cedar policies (all 4 rules), gateway auth + identity propagation to tools, latency + cost-per-conversation measurement | Gateway, Policy, Identity (outbound), Observability (latency/cost) | Gateway deny-rule tests + latency/cost report | Provable refusal in the trace, cost & latency |
| **D** | **Action & Approval** | Action lifecycle state machine + audit log, Runtime #2 + A2A *server* + agent card + off switch, `draft_email` / `send_approved_email` / `create_ticket`, stored-state check before send, SES approval email + callback (single-use, request-bound, expiring tokens), outcome reporting | Runtime (#2), Identity (A2A auth), Evaluations (trajectory) | Action scenarios (14) + approval attack tests | Live approval loop |

**Everyone does:**
- Deploys their own Phase 0 spike, so all four get hands on AgentCore Runtime.
- Writes their workstream's section of `docs/design.md` and their part of `docs/results/`.
- Owns unit + integration tests for their code.
- Tears down their own resources at the end (teardown order in §9).

### 2.1 Architecture by owner

`[A]`–`[D]` = owner. `(+)` = added to the team's original sketch because the brief requires it.

```
 ┌──────────────────────────────────────────────────────────────┐
 │ Client Web App                                           [A] │  chat client + sign-in
 └──────────────────────────────┬───────────────────────────────┘
                                │
 ┌──────────────────────────────▼───────────────────────────────┐
 │ Amazon Cognito                                           [A] │  8 test users, login → user_id;
 └──────────────────────────────┬───────────────────────────────┘  unsigned calls rejected before any model
                                │ JWT
 ┌──────────────────────────────▼───────────────────────────────────────────────┐
 │ Runtime #1                                                               [A] │
 │ (+) AgentCore Memory   [A]  short-term window + per-client long-term memory  │
 │ (+) Bedrock Guardrails [B]  input/output on every agent; account/SSN masking │
 │                                                                              │
 │  ┌─────────────────────────────────────────────────────────────────────────┐ │
 │  │ Coordinator Agent (no business tools)                               [A] │ │
 │  │  • routes each task; destination checked against a fixed agent list     │ │
 │  │  • limits: ≤4 hand-offs, no agent twice, ≤3 tool rounds, call ceiling   │ │
 │  │  • writes the reply only from specialist reports                        │ │
 │  │  • refuses off-topic / investment advice; degrades if Action is down    │ │
 │  └──────┬──────────────────────────┬──────────────────────────┬────────────┘ │
 │         │ task / report            │ task / report            │              │
 │  ┌──────▼─────────────────┐  ┌─────▼──────────────────┐       │              │
 │  │ Support Agent      [B] │  │ Research Agent     [C] │       │              │
 │  │ • answers only from KB │  │ • read-only: funds +   │       │              │
 │  │ • Sources: [... vX]    │  │   own holdings         │       │              │
 │  │ • gap → "I don't have  │  │ • tool failure is      │       │              │
 │  │   that information"    │  │   reported, never      │       │              │
 │  │ • ignores planted      │  │   filled in            │       │              │
 │  │   instructions         │  │                        │       │              │
 │  └──────┬─────────────────┘  └─────┬──────────────────┘       │              │
 │         │                          │                          │              │
 └─────────┼──────────────────────────┼──────────────────────────┼──────────────┘
           │                          │                          │ A2A (authenticated)
           │                          │                          │ client side [A] / server side [D]
 ┌─────────▼──────────────┐           │          ┌───────────────▼───────────────┐
 │ Knowledge Base     [B] │           │          │ Runtime #2                [D] │
 │ • 18 docs in S3 +      │           │          │ Action Agent              [D] │
 │   metadata files       │           │          │ • own role, agent card,       │
 │ • section / Q&A chunks │           │          │   off switch                  │
 │ • v3.1 filtered out    │           │          │ • only accepts the            │
 │ • calibrated threshold │           │          │   Coordinator as caller       │
 └─────────┬──────────────┘           │          └───────────────┬───────────────┘
           │ via gateway or direct    │                          │
           │ (decision D6)       [B]  │                          │
 ┌─────────▼──────────────────────────▼──────────────────────────▼───────────────┐
 │ AgentCore Gateway + Policy Engine                                         [C] │
 │ • tools grouped into targets: catalog-read / client-read / action-write       │
 │ • authenticates callers; passes the signed-in user_id to the tools            │
 │ • Cedar rules: only Action writes · send requires APPROVED ·                  │
 │   Research read-only · email only the assigned advisor                        │
 │ • every denial appears in the trace                                           │
 └──────────────┬─────────────────────────────────────────────┬──────────────────┘
                │                                             │
 ┌──────────────▼────────────────────────┐  ┌─────────────────▼────────────────────────┐
 │ Read operations — AWS Lambda      [C] │  │ Write operations — AWS Lambda        [D] │
 │ get_fund · get_fund_returns ·         │  │ draft_email · send_approved_email ·      │
 │ search_funds · get_my_holdings ·      │  │ create_ticket                            │
 │ get_my_advisor                        │  │ • tickets masked, description = data     │
 │ • typed input, no client ID argument  │  │ • send re-checks stored state first      │
 │ (+) also called by Action [C+D]       │  │                                          │
 └──────────────┬────────────────────────┘  └─────────────────┬────────────────────────┘
                │                                             │
 ┌──────────────▼────────────────────────┐  ┌─────────────────▼────────────────────────┐
 │ Fund / client DB (DynamoDB)       [C] │  │ Action requests + audit log + tickets[D] │
 │ Funds · Clients · Holdings · Advisors │  │ DRAFTED → PENDING_APPROVAL → APPROVED →  │
 │ loaded from p3-corpus/data            │  │ EXECUTED  (or DECLINED/EXPIRED/FAILED)   │
 └───────────────────────────────────────┘  │ code-only changes, every change audited  │
                                            └─────────────────┬────────────────────────┘
                                                              │
                                            ┌─────────────────▼────────────────────────┐
                                            │ Amazon SES → Approval email          [D] │
                                            │ to the APPROVER: what, to whom, why +    │
                                            │ Approve / Decline links                  │
                                            └─────────────────┬────────────────────────┘
                                                              │ approver clicks
                                            ┌─────────────────▼────────────────────────┐
                                            │ (+) API Gateway → Approval callback  [D] │
                                            └─────────────────┬────────────────────────┘
                                                              │
                                            ┌─────────────────▼────────────────────────┐
                                            │ Approval validation                  [D] │
                                            │ • token single-use, bound to 1 request,  │
                                            │   expires                                │
                                            │ • approve only if PENDING (conditional   │
                                            │   write)                                 │
                                            │ • bad link → generic page, logged        │
                                            └─────────────────┬────────────────────────┘
                                                              │
                                            ┌─────────────────▼────────────────────────┐
                                            │ Execute requested action             [D] │
                                            │ (+) SES → the ADVISOR (real email)       │
                                            │ → EXECUTED, or FAILED + reason           │
                                            │   (Dana Okafor: unverified, must fail)   │
                                            │ → reported on the client's next turn     │
                                            └──────────────────────────────────────────┘

 (+) Across everything: AgentCore Observability: one trace per turn, linked per session [A];
     latency p50/p95 + cost per conversation + budget alarm [C];
     AgentCore Evaluations: shared runner [B]; suites owned by A (routing), B (support), D (actions)
```

**Shared boundaries** (both owners must agree on the interface):

| Boundary | Owners | Agree on |
|---|---|---|
| Coordinator ↔ Support / Research | A ↔ B, A ↔ C | Task/report schema |
| A2A link | A ↔ D | Authentication, agent card, timeout behavior |
| Action → Gateway (reads + writes) | D ↔ C | Write targets; Cedar rules that check request state |
| Gateway → read tools | C ↔ all | Tool I/O models, identity propagation |
| Guardrails / masking | B ↔ all | Every agent and log uses B's helpers |

---

## 3. Shared contracts (agree in Phase 0; owner has final say)

These let all four tracks build in parallel against stubs. Put them in `src/common/contracts/`.

| Contract | Owner | Consumers |
|---|---|---|
| Tool input/output Pydantic models (all 8 tools) | C (reads), D (writes) | A, B, C, D |
| Action request lifecycle: states, allowed transitions, audit entry shape | D | A, C (Cedar policies check it) |
| Specialist task / report schema + routing enum | A | B, C, D |
| Citation format + KB document metadata schema | B | A |
| Masking + structured logging helpers (`src/common/`) | B (masking), C (logging) | All |
| Identity context (how `user_id` travels from Cognito JWT → runtime → gateway → tool) | A + C | All |

---

## 4. Fixed constraints (can't change)

| Area | Requirement |
|---|---|
| Models | Amazon Bedrock (justify choice). `amazon.nova-lite-v1:0` is known to work. |
| Framework | **LangGraph** (the brief allows LangGraph or Strands; the team chose LangGraph). Used for all agents in both runtimes. |
| AgentCore | **All 7:** Runtime, Gateway, Policy, Identity, Memory, Evaluations, Observability |
| AWS | Bedrock KB, Guardrails, Lambda, DynamoDB, S3, SES, API Gateway, Cognito, CloudWatch |
| Language | Python 3.11+, Pydantic v2, pytest |
| Topology | 2 runtimes (Coordinator side + Action), A2A between them, consequential tools behind Gateway |
| Tools | Exact names: `get_fund`, `get_fund_returns`, `search_funds`, `get_my_holdings`, `get_my_advisor`, `draft_email`, `send_approved_email`, `create_ticket`. No client-ID args, no open-ended queries. |
| Lifecycle | `DRAFTED → PENDING_APPROVAL → APPROVED → EXECUTED`; side exits `DECLINED`, `EXPIRED`, `FAILED`; `DRAFTED → EXECUTED` only for no-approval actions. Only code changes state; every change is audited (timestamp + actor); illegal transitions are refused and logged. |
| Limits | ≤4 hand-offs/turn · no specialist twice/turn (unless justified) · ≤3 tool rounds/specialist · tool-call ceiling per conversation (in code) · max tokens 1,024 coordinator / 2,048 specialists |
| Citations | `Sources: [Account Transfer Policy v3.2, s.4] [Fee Schedule FAQ, 2026-01]` |
| Gap reply | "I don't have that information in my documents. Would you like me to open a ticket?" |
| Latency p95 | Routing <3s · KB retrieval <1s · Support <8s · Research <10s · Action draft <12s |

---

## 5. Decisions to make early (record each in `docs/design.md` with reasoning)

The owner proposes, the team agrees.

| # | Decision | Owner | Starting recommendation |
|---|---|---|---|
| D1 | Framework | A | **Decided: LangGraph** (Strands ruled out by the team). Implications to plan for: <br>• Coordinator = a `StateGraph` with a router node whose output is a Pydantic model with a `Literal`/enum destination, so routing can't invent an agent. Hand-off and tool-round counters live in graph state and are checked on conditional edges. <br>• Each specialist = its own subgraph that receives only its task (no shared message history) and returns a report. <br>• Gateway tools are MCP tools via `langchain-mcp-adapters`, and **every node that calls them must be `async`** (§15). <br>• No built-in A2A: the Action runtime needs an A2A server wrapper (e.g. the `a2a-sdk` package around the LangGraph graph) and the Coordinator needs an A2A client node (D builds the server, A the client). Spike this in Phase 0. <br>• Models via `langchain-aws` (`ChatBedrockConverse`) with `max_tokens` set per node (1,024 / 2,048). <br>• Memory: use AgentCore Memory directly or through its LangGraph checkpointer/store integration, with keys namespaced by `user_id`. |
| D2 | Model(s) | A | Start on Nova Lite (known to work, cheap). Try a stronger model for the Coordinator/Support if routing or faithfulness scores lag. Pick based on eval scores + cost. |
| D3 | Hosting Coordinator / Support / Research | A | All three in Runtime #1 as in-process sub-agents (cheapest, simplest; isolation comes from separate prompts, contexts and gateway identities). Action in Runtime #2, **deployed as its own project** (avoids the `kms:TagResource` issue). |
| D4 | Final lifecycle | D | Use the brief's lifecycle as-is. Add an `EXECUTING` state only if you need it to guarantee no double sends. Freeze it by end of Phase 1. |
| D5 | Gateway target grouping | C | Group by policy: `catalog-read` (fund tools), `client-read` (my holdings/advisor), `action-write` (draft/send/ticket). This keeps each Cedar rule to one target. |
| D6 | KB retrieval: gateway or direct? | B | Decide with reasoning. Behind the gateway = audited and stoppable. Direct = faster, with fewer moving parts. (A13 notes either is fine.) |
| D7 | Tickets need approval? | D | Recommend **no** (internal, not leaving the building) → `DRAFTED → EXECUTED`. Put it in the policy matrix. |
| D8 | Custom Cedar rule (§6.4 #4) | C | "Action may only email `to_role = advisor`, resolved server-side to the client's assigned advisor." |
| D9 | Approval link design | D | Random single-use token, stored hashed in DynamoDB, bound to `request_id` + decision. Consumed with a **conditional write**. TTL ~24h (justify: approver turnaround vs exposure). |
| D10 | Chunking + relevance threshold | B | Policies chunked by numbered section, FAQs by Q&A pair, with header metadata (title, version, effective, status). Calibrate the threshold from score distributions on in-corpus vs gap questions. |
| D11 | Superseded handling | B | Metadata `status=superseded` on v3.1 + retrieval filter, plus a test. Keep v3.1 indexed to show the filter works. |
| D12 | Memory | A | Short-term: last N turns (justify N). Long-term: user-preference strategy, namespaced by **`user_id` from the token**. |
| D13 | Vector store | B | Cheapest that works (e.g. S3 Vectors or a serverless option). Tear down when idle. |
| D14 | Ticket store | D | DynamoDB table + ticket number returned immediately (policy §3.1). |
| D15 | IaC | C | Runtimes and AgentCore resources: the AgentCore CLI (`@aws/agentcore`, which replaces the unsupported starter toolkit) and the TypeScript CDK app it generates per project. Surrounding AWS resources: CDK, in a language C picks. |

---

## 6. Prep checklist (before building)

### Accounts & access
- [ ] **(all)** Bedrock access confirmed with a **one-line invoke** (`amazon.nova-lite-v1:0`) plus an embedding model. *A: Nova Lite confirmed in us-east-1 (2026-11-11); embedding model still to check (B).*
- [x] **(all)** Region chosen where all 7 AgentCore services are available: **us-east-1**.
- [ ] **(C)** **AWS Budget / CloudWatch billing alarm** created on day 1.
- [ ] **(D)** SES (sandbox): verify the approver address + `you+jordan@`, `you+priya@`, `you+marcus@` addresses. **Never verify Dana Okafor (adv-04).** Send one test email to each and confirm delivery.

### Repo & shared environment
- [ ] Public GitHub repo; project board with one column/label per workstream.
- [ ] `.gitignore` (venv, `.env`, `cdk.out`, eval outputs). Secret scanning on (e.g. gitleaks pre-commit). **No account IDs/keys in history.**
- [ ] `pyproject.toml` / `requirements.txt`; ruff + pytest; GitHub Actions running unit tests.
- [ ] Shared AWS account: every resource name prefixed and tagged by owner/workstream (e.g. `p3-c-gateway`) so each person can find and tear down their own.
- [ ] Layout (owners in brackets):
  ```
  src/
    common/        # contracts, masking, logging, config        [all]
    coordinator/   # coordinator + routing + limits + memory    [A]
    support/       # support agent                              [B]
    research/      # research agent                             [C]
    tools/         # Lambda tool handlers                       [C reads, D writes]
    action/        # action agent (runtime #2)                  [D]
    lifecycle/     # state machine + audit log                  [D]
    approval/      # SES approval email + callback Lambda       [D]
  p3coordinator/   # AgentCore CLI project for Runtime #1       [A]
  infra/           # IaC, one stack per workstream              [all]
  loaders/         # DynamoDB / Cognito / S3+KB metadata        [C, A (Cognito), B (KB metadata)]
  tests/           # unit/ integration/ e2e/                    [all]
  evals/           # AgentCore Evaluations configs + runner     [B runner, each owns a suite]
  docs/            # design.md, diagrams, results/              [all]
  Project3-Corpus-Documents/p3-corpus/   # provided data (read-only; report errors, don't edit)
  ```

---

## 7. Phased roadmap

> Phases 0–1 are done together. Phase 2 runs as four parallel tracks. Integration milestones (M1–M4) are where tracks join up, and the regression evals run at each one.

### Phase 0: Foundations & spikes (all)
- [ ] Prep checklist complete.
- [ ] One spike per person, so everyone deploys something real:
  - **A:** hello-world agent on AgentCore Runtime, called with a Cognito JWT. *Partly done (2026-11-11): Runtime #1 (`coordinator`) is deployed and invoked with IAM auth. The Cognito JWT part moves to Track A step A3.*
  - **B:** Bedrock KB over 2–3 docs + one retrieval call with scores.
  - **C:** Gateway with one Lambda target + one Cedar policy (with conditions; the analyzer rejects condition-less policies), shown allowing and denying.
  - **D:** second runtime (its own project) running a LangGraph graph behind an A2A server wrapper, called over A2A from A's spike runtime. This is the riskiest spike, since LangGraph has no built-in A2A.
- [ ] Draft the architecture diagram and the D1–D15 decisions together.
- **Exit:** all four spikes work, and the shared contracts (§3) are drafted.

### Phase 1: Contracts & data (all, C leads)
- [ ] Freeze the shared contracts in `src/common/contracts/` with stub implementations.
- [ ] **C:** DynamoDB tables (Funds, Clients/Accounts, Holdings, Advisors, ActionRequests, AuditLog, Tickets, ApprovalTokens) + idempotent loaders from `data/*.json`. Advisor emails are swapped in from config (not git), and adv-04 is left unverified.
- [ ] **A:** Cognito user pool + 8 test users mapped to `user_id` (custom attribute); passwords in Secrets Manager, not git.
- [ ] **B:** S3 KB docs + `.metadata.json` sidecars.
- [ ] **D:** lifecycle module first draft: Pydantic models, allowed-transition table, conditional-write transitions, audit entry on every change (actor = agent/client/approver).
- **Exit:** sanity checks pass (u-001 has 5 positions, about $110,900; u-004 has none). The lifecycle is documented and frozen.

### Phase 2: Parallel tracks

#### Track A: Orchestration & Memory
- [ ] Coordinator: structured routing output validated against the **specialist enum** (can't invent a destination). Writes replies only from specialist reports.
- [ ] Specialists get a task + return a report (no shared conversation); log exactly what each one was told.
- [ ] Limits in code: 4 hand-offs, 1 use per specialist, 3 tool rounds, per-conversation tool ceiling, token caps. Graceful "I stopped here" message.
- [ ] Refusals: off-topic, investment advice (decline + offer the advisor), prompt attacks (with B's guardrails).
- [ ] Inbound auth: unsigned calls rejected before any model runs.
- [ ] A2A client to the Action runtime; Action runtime down → finish what's possible + say so.
- [ ] AgentCore Memory: short-term window + long-term preferences per `user_id`; memory down → continue. Recall tests wait for extraction (it takes minutes).
- [ ] Bounded retry on throttling/timeouts.
- [ ] One trace per turn, turns linked by session.
- **Exit:** R01–R46 routing eval meets target, memory recall + cross-client isolation tests pass.

**Track A order** (each step is its own branch and PR):
1. **A1 Routing eval + refusal fix.** Score R01–R46 against the real router (3 runs, report in `docs/results/`), then fix misses. Known miss: "Should I sell my bond fund?" isn't refused as investment advice. Needs Bedrock only.
2. **A2 Limits and hardening.** Call `verify_report` (`common/contracts/protocol.py`) on every report, add the per-conversation tool-call ceiling and the "I stopped here" reply, and add bounded retries on Bedrock throttling.
3. **A3 Cognito + verified identity.** User pool, 8 test users, JWT authorizer on Runtime #1, and `VerifiedIdentityContext` built from the token and passed to specialists out of band. Unblocks **M1** (B) and **M2** (C).
4. **A4 A2A client to Action.** Agree with D that the A2A message carries `ActionA2ARequest` JSON and the artifact returns `ActionA2AResponse` JSON, and agree how `user_id` reaches Action. Runtime #1 finds Action through `ACTION_RUNTIME_ARN`. Unblocks **M3**.
5. **A5 AgentCore Memory.** Short-term window plus long-term preferences, namespaced by `user_id` from A3. Memory down → the turn continues.
6. **A6 Tracing.** One trace per turn including the A2A hop, with turns linked by session.
7. **A7 Docs and demo.** `docs/design.md` sections and decisions D1–D3, D12.

#### Track B: Knowledge & Safety
- [ ] Bedrock KB with section/Q&A-aware chunking (custom chunking or pre-split files) + metadata.
- [ ] Superseded filter (v3.2 wins); documents treated as data in the prompt + guardrail.
- [ ] Support agent + citation formatter in the required format. Check that each citation actually supports the claim.
- [ ] **Threshold calibration:** plot scores for answerable vs gap/near-miss questions, pick the cut-off, save the evidence.
- [ ] Show **one retrieval improved** by the chunking choice (before/after).
- [ ] Log gap questions (§12).
- [ ] Guardrails on input + output: investment-advice denied topic + 1 custom topic, content filters, prompt-attack filter.
- [ ] Masking of account numbers / SSN-like strings **before** logs, traces and memory (shared helper used by everyone).
- [ ] Shared eval runner (AgentCore Evaluations): one command → `docs/results/run-YYYYMMDD-N.md`.
- **Exit:** 25/25 `support_qa` correct, Q01–Q05 cite v3.2, Q25 gives the gap reply, injection doc ignored, masking proven in a trace.

#### Track C: Data, Tools & Gateway
- [ ] 5 read tools as Lambdas with typed Pydantic inputs. `get_my_*` read `user_id` from the propagated identity only.
- [ ] Research agent (read-only); malformed tool data → report the failure, never fill in missing data.
- [ ] Gateway targets per D5; inbound auth on the gateway; per-agent workload identities.
- [ ] Cedar policies: (1) only Action can write, (2) send requires approved, (3) Research read-only, (4) custom rule D8.
- [ ] Code-level audit logging of every tool call.
- [ ] Integration tests: **each deny rule denies at the gateway and shows in the trace**; cross-client read impossible.
- [ ] Latency p50/p95 harness for the 5 operations; cost-per-conversation from trace token counts.
- **Exit:** R16–R25 correct; A09/R46 never leak u-001 data; A14 turn 1 returns LFGR5 / 3.01%; policy matrix + "which layer catches which failure" table drafted.

#### Track D: Action & Approval
- [ ] Lifecycle module finished: every legal transition tested, every illegal one refused + logged (drafted→executed for emails, approve twice, etc.).
- [ ] Action agent (LangGraph graph) in Runtime #2, own execution role, A2A server wrapper + **agent card**; refuses callers other than the coordinator.
- [ ] Off switch (a flag, or disabling the runtime/target) that leaves Support/Research working.
- [ ] `draft_email` → `PENDING_APPROVAL` + SES approval email to the approver (what, to whom, why, Approve/Decline links).
- [ ] Approval callback (API Gateway + Lambda): single-use, request-bound, expiring token. Generic "link invalid or expired" page. Approver ≠ requester.
- [ ] `send_approved_email` **re-reads stored state** and refuses unless `APPROVED`. Then SES send → `EXECUTED` or `FAILED (reason)`; adv-04 fails cleanly.
- [ ] Outcome reported to the client on their next turn (with A).
- [ ] `create_ticket` with the 7 categories, account numbers masked, description stored as data.
- **Exit:** replay, tampering, late use, "approver already said yes" (A07) and unverified advisor (A04) all handled; A01–A14 pass by hand.

### Integration milestones

| Milestone | What works end to end | Who |
|---|---|---|
| **M1 Thin slice** | Signed-in user → Coordinator → Support answer with a correct citation; gap question gets the gap reply | A + B |
| **M2 Reads** | Research answers via the gateway; a cross-client request is denied, and the denial is in the trace | A + C |
| **M3 Action loop** | "Summarize my holdings and email my advisor": holdings → draft → approval email → live click → sent → reported next turn | All |
| **M4 Hardened** | All three eval suites run 3+ times with scores recorded; every §10.2 test automated; every §12 failure exercised | All |

The regression eval runs at every milestone, and scores go in the progress log (§13).

### Final phase: Docs, demo, teardown (all)
- [ ] `docs/design.md`: each owner writes their section. Covers the diagram (A), lifecycle (D), tool grouping + policy matrix (C), A2A agent card (D), chunking + threshold evidence (B), layer-vs-failure table (C), and all D-decisions (each owner).
- [ ] `docs/results/`: test results, eval scores ×3, latency + cost (C), **worst failure paragraph** (team picks one).
- [ ] README: setup, deploy, seed, run tests/evals, teardown.
- [ ] Demo rehearsed and timed (see §8).
- [ ] Teardown: **delete Cedar policies before the policy engine**, then runtimes, gateway, KB, vector store. Each person tears down their prefixed resources, and the team captures CLI output/screenshots as evidence.

---

## 8. Demo split (§13)

| Order | Segment | Presenter |
|---|---|---|
| 1 | Intro, architecture diagram, how routing + memory work | A |
| 2 | Grounded policy answer with a citation, then the gap question | B |
| 3 | Full approval loop with a live click, outcome reported next turn | D |
| 4 | Provable refusal (cross-client or attack) shown in the trace; cost & latency numbers | C |
| 5 | Surprise live question from the reviewers | All (owner of that area answers) |

---

## 9. §10.2 test coverage map

| Category | Test | Ground-truth link | Owner |
|---|---|---|---|
| Boundaries | Question just under the relevance threshold | (custom) | B |
| | Support-or-Research ambiguous message | R24 | A |
| | Exactly 4 hand-offs | (custom) | A |
| Failures | Action runtime slow/down → degrade | (custom, real timeout) | A + D |
| | Tool returns malformed data | (custom) | C |
| | Every gateway deny rule denies (in trace) | A07 + custom | C |
| | Another client's holdings refused | A09, R46 | C |
| Attacks | Planted document instruction | Statements FAQ injection case | B |
| | Ticket description read-back injection | A12 | D |
| | "Approver already said yes" | A07 | D |
| Honesty | Gap → "I don't have that" | Q25, R15 | B |
| | Superseded never cited | Q01–Q05, A13 | B |
| Approval | Replay / tampering / late use | (custom) | D |
| | Unverified advisor fails cleanly | A04 | D |
| Memory | Cross-session recall | (custom) | A |
| | Cross-client isolation | (custom) | A |

## 10. Test users quick reference

| User | Why they matter |
|---|---|
| u-001 Alex Morgan | Happy path: 5 positions / 2 accounts, about $110,900, advisor Jordan Ellis (A01–A03, A13) |
| u-002 Sam Patel | Third-party email refused (A06), account-number masking (A11) |
| u-003 Riley Chen | Memory across turns (A14), self-approval attempt (A07), advisor Priya Raman |
| u-004 Taylor Brooks | Account but **no holdings** (A05) |
| u-005 | Fee ticket (A08), ticket injection (A12) |
| u-006 Casey Nguyen | **Unverified advisor** Dana Okafor → send must fail (A04) |
| u-007 | Cross-user request (A09) |
| u-008 | Suspected-fraud access ticket, same-day handling (A10) |

## 11. Platform gotchas (from §15)
- Bare 500 from a new runtime → usually a blocked model. Test with a one-line Bedrock call first.
- Second runtime → deploy as its **own project** (`kms:TagResource` failure). *(D)*
- MCP tools are async-only. In LangGraph, **the node that calls them must itself be `async`**; running the graph with `ainvoke` doesn't fix a synchronous node. *(A, C, D: applies to every agent that calls gateway tools)*
- Cedar analyzer rejects condition-less policies. Add conditions; don't override the check. *(C)*
- Delete policies **before** the policy engine, or the stack delete breaks. *(C)*
- Memory takes minutes to activate, and long-term extraction lags. Add waits to recall tests. *(A)*
- SES sandbox only delivers to verified addresses. Verify and prove a send early. *(D)*
- Vector stores bill while idle. Tear down or pick the cheapest. *(B)*
- The `AI-TFBD` SSO permission set **can't deploy**: it lacks `iam:AttachRolePolicy`, which CDK bootstrap and runtime roles need. Deploy with the team deploy IAM user (ask the account admin). CDK is bootstrapped in us-east-1. *(all)*
- A failed bootstrap leaves the shared `CDKToolkit` stack in `ROLLBACK_COMPLETE`, and every deploy then stops. Someone with permission has to delete the stack before the next deploy re-creates it. Check for a leftover `cdk-hnb659fds-assets-*` bucket first. *(all)*
- PowerShell 5.1 strips the quotes from JSON passed to native commands (curl, `npx`). Use `npx --% agentcore invoke ... --payload "{\"prompt\":\"...\"}"`, `Invoke-RestMethod`, or Git Bash. *(all)*
- The `p3coordinator` runtime installs `assistant/src` as a **snapshot**, not an editable install. After editing `src/`, run `uv sync --reinstall-package p3-agentcore-assistant` in `p3coordinator/app/coordinator` and delete `p3coordinator/agentcore/.cache/coordinator`, or `agentcore dev` and `deploy` keep running old code. *(A, and anyone whose specialist runs in Runtime #1)*
- Run `npx agentcore` from the project folder (e.g. `assistant/p3coordinator`), or it reports "No AgentCore project found". *(all)*
- Each AgentCore project's `agentcore/aws-targets.json` and `agentcore/.cli/` hold the account ID and ARNs. Keep them untracked. *(all; note: `actionfolder/Action/agentcore/aws-targets.json` is currently tracked, D)*

## 12. Acceptance checklist tracker (§16)

| Done | Outcome | Owner | When |
|---|---|---|---|
| [ ] | Lifecycle documented + enforced by code | D | Phase 1 / Track D |
| [ ] | Action isolated in own runtime, authenticated A2A | D (+ A client side) | Track D |
| [ ] | Routing validated + bounded; specialists isolated | A | Track A |
| [ ] | Data loaded; placeholders replaced; adv-04 unverified | C (+ D for SES) | Phase 1 |
| [ ] | Grounded, cited support answers; justified chunking + calibrated threshold | B | Track B |
| [ ] | Consequential tools behind gateway; reads scoped to signed-in client | C | Track C |
| [ ] | Cedar policies + stored-state check before send | C (policies), D (state check) | Tracks C + D |
| [ ] | Email approval survives replay / tampering / late use | D | Track D |
| [ ] | Memory within + across sessions, isolated per client | A | Track A |
| [ ] | Guardrails, masking, output caps, tool-call ceiling | B (guardrails, masking), A (caps, ceiling) | Tracks A + B |
| [ ] | Evaluations as regression suite, scores per run | B (runner), each owner (suite) | M1–M4 |
| [ ] | Every §10.2 item has an automated test | Per §9 | M4 |
| [ ] | Traces, latency, cost per conversation, budget alarm | A (traces), C (latency, cost, budget) | Tracks A + C |
| [ ] | Every §12 failure situation exercised | A (throttle, memory, Action down), C (tool fail), D (policy deny, bad link), B (gap) | M4 |
| [ ] | Design doc, results, live demo, teardown evidence | All | Final phase |

## 13. Open questions for the instructor / team
- Names of the 4 team members and who takes which workstream (A–D).
- Deadline and demo length (affects how much to build vs polish).
- Is a minimal UI expected, or is a CLI/notebook client acceptable for the demo?
- Shared AWS account constraints (SCPs, regions, budget cap)?

## 14. Progress log
| Date | Owner | Phase / Milestone | What changed | Eval scores (Routing / Support / Actions) |
|---|---|---|---|---|
| 2026-11-11 | A | Phase 0 | Runtime #1 (`coordinator`) deployed to us-east-1 with the AgentCore CLI: Nova Lite router, stub specialists. Runtime and role ARNs shared with D (not in git). | Routing: baseline pending (A1) / – / – |
| 2026-11-11 | A | Track A / A1 | Routing eval harness (`evals/routing/run_routing.py`, `coordinator/routing_eval.py`); router prompt rewritten (refuse first, action only when asked, how-to → support) + 1 bounded retry. Known miss: R19 fund search over-refused. Reports `docs/results/routing-20261111-{1,3}.md`. | Routing (Nova Lite, 3 runs): 29–31/46 → **44–45/46** / – / – |
