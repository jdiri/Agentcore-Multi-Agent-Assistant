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

Run every `npx agentcore` command from `assistant/p3coordinator/`. From anywhere else, the CLI reports "No AgentCore project found".

To run through the CLI with no AWS access, put `P3_STUB_ROUTER=1` in `p3coordinator/agentcore/.env.local`, then from `p3coordinator/`:

```
npx agentcore dev
npx agentcore invoke --runtime coordinator --local --payload '{"prompt": "What are your fees?"}'
```

Remove `P3_STUB_ROUTER=1` to use the real Nova Lite router locally. It then needs AWS credentials in that terminal.

### AWS credentials

The `AI-TFBD` SSO role **can't deploy**: it lacks `iam:AttachRolePolicy`, which CDK needs. Deploy with the team deploy IAM user (ask the account admin for an access key):

```
aws configure --profile <profile>     # access key, secret, us-east-1, json
$env:AWS_PROFILE = "<profile>"        # bash: export AWS_PROFILE=<profile>
aws sts get-caller-identity           # the ARN should end in :user/...
```

Keys live only in `~/.aws/credentials`, never in the repo or `.env.local`. CDK is already bootstrapped in us-east-1.

### Deploy and invoke

```
npx agentcore deploy
npx agentcore status                  # runtime and role ARNs (share them in the team channel, not git)
```

Invoke from Git Bash:

```
npx agentcore invoke --runtime coordinator --payload '{"prompt": "What are your fees?"}'
```

PowerShell 5.1 strips the quotes from JSON passed to `npx`, so use the stop-parsing token `--%`:

```
npx --% agentcore invoke --runtime coordinator --payload "{\"prompt\":\"What are your fees?\"}"
```

### Troubleshooting

| Symptom | Fix |
|---|---|
| `No AgentCore project found` | Run from `assistant/p3coordinator/` |
| `400` from the runtime, or `too many arguments for 'invoke'` | PowerShell quoting. Use `--%` or Git Bash |
| `The shared CDKToolkit stack is in 'ROLLBACK_COMPLETE'` | A failed bootstrap. Delete the `CDKToolkit` stack with the deploy IAM user, then deploy again |
| `AccessDenied ... iam:AttachRolePolicy` | You are on the SSO role. Switch `AWS_PROFILE` to the deploy IAM user |
| Bare `500` | `npx agentcore logs`. Usually Bedrock model access |
| `dev` or the deployed runtime runs old code after you edit `assistant/src` | The runtime installs `src/` as a snapshot. From `p3coordinator/`: `cd app/coordinator; uv sync --reinstall-package p3-agentcore-assistant; cd ../..`, and delete `agentcore/.cache/coordinator` before deploying |

`aws-targets.json` and `agentcore/.cli/` hold the AWS account ID and ARNs, so they stay out of git. Teardown steps will be added as the stacks are built.

Never commit AWS keys, account IDs or `.env` files.
