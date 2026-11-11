from langchain.agents import create_agent
from opentelemetry.instrumentation.langchain import LangchainInstrumentor
from a2a.utils import new_task
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import AgentCapabilities, AgentCard, AgentInterface, AgentSkill, Part
from bedrock_agentcore.runtime import serve_a2a
from model.load import get_model
from tools import draft_email, send_approved_email, create_ticket


LangchainInstrumentor().instrument()


# @tool
# def add_numbers(a: int, b: int) -> int:
#     """Return the sum of two numbers."""
#     return a + b



tools = [draft_email, send_approved_email, create_ticket]

SYSTEM_PROMPT = """
You are the Action Agent for a financial assistant.

You execute authorized actions using the tools provided.
Never perform actions outside your available tools.
Always verify approval before sending an email.

"""

model = get_model()

graph = create_agent(
    model=model,
    tools=tools,
    system_prompt=SYSTEM_PROMPT
)



# Executor updates a given task rather than returning some results. Caller needs to look for those updates.
class LangGraphA2AExecutor(AgentExecutor):
    """Wraps a LangGraph CompiledGraph as an a2a-sdk AgentExecutor."""

    def __init__(self, graph):
        self.graph = graph

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        task = context.current_task or new_task(context.message)
        if not context.current_task:
            await event_queue.enqueue_event(task)
        updater = TaskUpdater(event_queue, task.id, task.context_id)

        user_text = context.get_user_input()
        result = await self.graph.ainvoke({"messages": [("user", user_text)]})
        response = result["messages"][-1].content

        await updater.add_artifact([Part(text=response)])
        await updater.complete()

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        pass


# describes what the agent can do
# A2A version of MCP's tools/list
card = AgentCard(
    name="ActionAgent",
    description="A LangGraph Action Agent on Bedrock AgentCore",
    version="0.1.0",
    url="http://localhost:9000/",
    capabilities=AgentCapabilities(streaming=True),
    skills=[
        AgentSkill(
            id="draft_email",
            name="Draft Email",
            description="Create an email draft for approval",
            tags=["email"],
        ),
        AgentSkill(
            id="send_approved_email",
            name="Send Approved Email",
            description="Send an email after approval",
            tags=["email"],
        ),
        AgentSkill(
            id="create_ticket",
            name="Create Ticket",
            description="Create a support ticket",
            tags=["ticket"],
        ),
    ],
    default_input_modes=["text"],
    default_output_modes=["text"],
    supported_interfaces=[
        AgentInterface(
            protocol_binding="JSONRPC",
            protocol_version="1.0",
            transport="JSONRPC",
            url="http://localhost:9000/",
        )
    ],
)

if __name__ == "__main__":
    serve_a2a(LangGraphA2AExecutor(graph), card)