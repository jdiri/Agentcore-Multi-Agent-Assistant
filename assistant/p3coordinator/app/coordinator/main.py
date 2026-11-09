"""AgentCore CLI entrypoint for Runtime #1. The code lives in assistant/src/coordinator."""

from coordinator.runtime import app

if __name__ == "__main__":
    app.run()
