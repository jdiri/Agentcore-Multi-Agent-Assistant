from langchain_core.tools import tool
from langchain.agents import create_agent
from model.load import get_model
from langchain.messages import HumanMessage


@tool
def test_action(message: str) -> str:
    """Test that the Action Agent can invoke a tool."""
    return f"Action executed successfully: {message}"


model = get_model()

graph = create_agent(
    model=model,
    tools=[test_action],
    system_prompt="You are a test Action Agent. Use the test_action tool when requested."
)


async def main():
    result = await graph.ainvoke({
        "messages": [
            HumanMessage(content="Use the test_action tool with the message Hello.")
        ]
    })

    print(result["messages"][-1].content)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())