from typing import Annotated, Literal
from typing_extensions import TypedDict

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    SystemMessage,
)
from langchain_aws import ChatBedrockConverse

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from research.prompt import RESEARCH_SYSTEM_PROMPT
from research.mock_tools import (
    get_fund,
    get_fund_returns,
    search_funds,
    get_my_holdings,
    get_my_advisor,
)


MAX_TOOL_ROUNDS = 3


class ResearchState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    tool_rounds: int


# 1. Initialize Bedrock
model = ChatBedrockConverse(
    model_id="amazon.nova-lite-v1:0",
    region_name="us-east-1",
    max_tokens=2048,
    temperature=0,
)


# 2. Register available tools
tools = [
    get_fund,
    get_fund_returns,
    search_funds,
]

model_with_tools = model.bind_tools(tools)


# 3. Create the tool executor
tool_node = ToolNode(tools)


# 4. Model node
async def call_model(state: ResearchState):
    conversation = [
        SystemMessage(content=RESEARCH_SYSTEM_PROMPT),
        *state["messages"],
    ]

    # After 3 tool rounds, don't offer further tools.
    if state["tool_rounds"] >= MAX_TOOL_ROUNDS:
        conversation.insert(
            1,
            SystemMessage(
                content=(
                    "The tool execution limit has been reached. "
                    "Do not request more tools. Give a final answer "
                    "using only verified results already available. "
                    "Mention any information that remains unavailable."
                )
            ),
        )
        response = await model.ainvoke(conversation)
    else:
        response = await model_with_tools.ainvoke(conversation)

    return {"messages": [response]}


# 5. Conditional routing
def should_continue(
    state: ResearchState,
) -> Literal["tools", "__end__"]:

    last_message = state["messages"][-1]

    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        if state["tool_rounds"] >= MAX_TOOL_ROUNDS:
            raise RuntimeError("Research tool-round limit exceeded")

        return "tools"

    return END


# 6. Tool execution node
async def call_tools(state: ResearchState):
    result = await tool_node.ainvoke(state)

    return {
        "messages": result["messages"],
        "tool_rounds": state["tool_rounds"] + 1,
    }


# 7. Build the graph
def build_research_graph():
    builder = StateGraph(ResearchState)

    builder.add_node("call_model", call_model)
    builder.add_node("tools", call_tools)

    builder.add_edge(START, "call_model")

    builder.add_conditional_edges(
        "call_model",
        should_continue,
        {
            "tools": "tools",
            END: END,
        },
    )

    builder.add_edge("tools", "call_model")

    return builder.compile()