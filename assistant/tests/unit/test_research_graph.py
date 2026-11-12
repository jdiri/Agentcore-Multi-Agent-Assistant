import asyncio

from langchain_core.messages import HumanMessage

from research.graph import build_research_graph


async def main():
    graph = build_research_graph()

    result = await graph.ainvoke(
        {
            "messages": [HumanMessage(content="Look up fund LFGR5 using your research tool.")],
            "tool_rounds": 0,
        }
    )

    from langchain_core.messages import AIMessage, ToolMessage

    messages = result["messages"]

    tool_calls = [
        call
        for message in messages
        if isinstance(message, AIMessage)
        for call in message.tool_calls
    ]

    tool_results = [message for message in messages if isinstance(message, ToolMessage)]

    assert len(tool_calls) >= 1, "Model did not request a tool"
    assert tool_calls[0]["name"] == "get_fund"
    assert len(tool_results) >= 1, "Tool was not executed"
    assert result["tool_rounds"] == 1
    assert isinstance(messages[-1], AIMessage)
    assert not messages[-1].tool_calls

    print("Research graph test passed!")

    for message in result["messages"]:
        print(f"\n{message.type.upper()}: {message.content}")

        if getattr(message, "tool_calls", None):
            print("TOOL CALLS:", message.tool_calls)

    print("\nTool rounds:", result["tool_rounds"])


if __name__ == "__main__":
    asyncio.run(main())
