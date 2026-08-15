"""图的编排流程"""

from langgraph.graph import StateGraph, START, END
from app.graphs.hospital.nodes.chat_node import chat_node
from app.graphs.hospital.nodes.tool_node import tool_node
from app.graphs.hospital.nodes.knowledge_node import knowledge_node
from app.graphs.hospital.nodes.intent_judgment_node import intent_judgment_node
from app.graphs.hospital.state import State


def route_by_intent(state: State) -> str:
    return state["intent"]


graph = StateGraph(State)

graph.add_node("chat", chat_node)
graph.add_node("tool", tool_node)
graph.add_node("knowledge", knowledge_node)
graph.add_node("intent_judgment", intent_judgment_node)

graph.add_edge(START, "intent_judgment")

graph.add_conditional_edges(
    "intent_judgment",
    route_by_intent,
    {
        "chat": "chat",
        "tool": "tool",
        "knowledge": "knowledge",
    },
)

graph.add_edge("chat", END)
graph.add_edge("tool", END)
graph.add_edge("knowledge", END)

app = graph.compile()


# 运行图
def run_graph(input: str) -> str:
    result = app.invoke(
        {
            "messages": [{"role": "user", "content": input}],
            "user_id": "1234567890",
        }
    )
    return result["messages"][-1].content
