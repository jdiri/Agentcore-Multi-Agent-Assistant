# Agentcore-Multi-Agent-Assistant

Multi-agent client-service assistant on AWS AgentCore for the fictional "Lanternfield" fund family.

**All funds, people, accounts and policies in this project are synthetic.** Do not present any of it as real financial data.

- Brief: [docs/project-blueprint.md](docs/project-blueprint.md)
- Team plan: [docs/roadmap.md](docs/roadmap.md)

## Setup

Requires Python 3.11 or newer. Run these from the `assistant/` folder.

```
python -m venv .venv
source .venv/bin/activate        # PowerShell: .venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pre-commit install               # enables the gitleaks secret scan on every commit
```

## Checks

```
pytest tests/unit
ruff check .
ruff format --check .
```

## Run the Coordinator locally

No AWS access is needed in stub mode. Routing uses keywords and every specialist is a stub.

```
P3_STUB_ROUTER=1 python src/coordinator/runtime.py
curl -X POST localhost:8080/invocations -H "Content-Type: application/json" -d '{"prompt": "Summarize my holdings and email my advisor"}'
```

In PowerShell:

```
$env:P3_STUB_ROUTER=1; python src/coordinator/runtime.py
Invoke-RestMethod -Method Post -Uri http://localhost:8080/invocations -ContentType "application/json" -Body '{"prompt": "Summarize my holdings and email my advisor"}'
```

To plug in a real specialist, write an async function that takes a `SpecialistTask` and returns a `SpecialistReport` (`src/common/contracts/routing.py`), then replace its entry in `STUB_SPECIALISTS` (`src/coordinator/stubs.py`).

## Runtime #1 with the AgentCore CLI

Runtime #1 is the AgentCore project in `p3coordinator/`. Its `app/coordinator/main.py` only imports the real code from `src/coordinator`, and the CLI packages `src/` with it. Requires Node 20.12+ and [uv](https://docs.astral.sh/uv/). Do not install the old Python starter toolkit, because it also provides an `agentcore` command.

```
npm install                     # from the repo root; installs @aws/agentcore, then use: npx agentcore ...
cd assistant/p3coordinator/agentcore/cdk && npm install && cd ../..
```

To run through the CLI with no AWS access, put `P3_STUB_ROUTER=1` in `p3coordinator/agentcore/.env.local`, then from `p3coordinator/`:

```
npx agentcore dev
npx agentcore invoke --runtime coordinator --local --payload '{"prompt": "What are your fees?"}'
```

To deploy (needs AWS credentials and a region):

```
npx agentcore deploy
npx agentcore invoke --runtime coordinator --payload '{"prompt": "What are your fees?"}'
```

`aws-targets.json` and `agentcore/.cli/` hold the AWS account ID and ARNs, so they stay out of git. Teardown steps will be added as the stacks are built.

Never commit AWS keys, account IDs or `.env` files.
