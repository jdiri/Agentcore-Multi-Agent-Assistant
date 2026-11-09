# Agentcore-Multi-Agent-Assistant

Multi-agent client-service assistant on AWS AgentCore for the fictional "Lanternfield" fund family.

**All funds, people, accounts and policies in this project are synthetic.** Do not present any of it as real financial data.

- Brief: [docs/project-blueprint.md](docs/project-blueprint.md)
- Team plan: [docs/roadmap.md](docs/roadmap.md)

## Setup

Requires Python 3.11 or newer.

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

Never commit AWS keys, account IDs or `.env` files. Deploy and teardown steps will be added as the stacks are built.
