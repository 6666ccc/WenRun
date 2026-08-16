"""患者端三业务 Agent 路由图。仅通过 build_graph 编译，禁止模块级单例。"""

from dataclasses import dataclass
from typing import Any

from langgraph.graph import END, START, StateGraph

from app.graphs.hospital.nodes.chat_node import build_chat_node
from app.graphs.hospital.nodes.citation_validate_node import (
    citation_validate_node,
    route_after_citation,
)
from app.graphs.hospital.nodes.clarify_node import build_clarify_node
from app.graphs.hospital.nodes.hospital_node import (
    build_hospital_node,
    route_after_hospital,
)
from app.graphs.hospital.nodes.intent_judgment_node import build_intent_judgment_node
from app.graphs.hospital.nodes.medical_node import build_medical_node
from app.graphs.hospital.nodes.memory_node import (
    build_load_memory_node,
    build_save_memory_node,
)
from app.graphs.hospital.nodes.registration_interrupt_node import (
    build_registration_interrupt_node,
)
from app.graphs.hospital.state import State


@dataclass
class GraphDependencies:
    intent_agent: Any
    chat_agent: Any
    hospital_agent: Any
    medical_agent: Any
    clarify_agent: Any | None = None
    hospital_retriever: Any | None = None
    medical_retriever: Any | None = None
    tools: Any | None = None
    vector_memory: Any | None = None


def graph_config(conversation_id: str, delegation_token: str | None) -> dict:
    return {
        "configurable": {
            "thread_id": conversation_id,
            "delegation_token": delegation_token,
        }
    }


def route_by_intent(state: State) -> str:
    intent = state.get("intent") if hasattr(state, "get") else getattr(state, "intent", None)
    if intent in {"chat", "hospital", "medical"}:
        return intent
    return "clarify"


def build_graph(deps: GraphDependencies, checkpointer=None):
    builder = StateGraph(State)
    builder.add_node("load_memory", build_load_memory_node(deps))
    builder.add_node("intent_judgment", build_intent_judgment_node(deps))
    builder.add_node("chat", build_chat_node(deps))
    builder.add_node("hospital", build_hospital_node(deps))
    builder.add_node("medical", build_medical_node(deps))
    builder.add_node("clarify", build_clarify_node(deps))
    builder.add_node("registration_interrupt", build_registration_interrupt_node(deps))
    builder.add_node("citation_validate", citation_validate_node)
    builder.add_node("save_memory", build_save_memory_node(deps))

    builder.add_edge(START, "load_memory")
    builder.add_edge("load_memory", "intent_judgment")
    builder.add_conditional_edges(
        "intent_judgment",
        route_by_intent,
        {
            "chat": "chat",
            "hospital": "hospital",
            "medical": "medical",
            "clarify": "clarify",
        },
    )
    for node in ("chat", "medical", "clarify"):
        builder.add_edge(node, "citation_validate")
    builder.add_conditional_edges(
        "hospital",
        route_after_hospital,
        {
            "registration_interrupt": "registration_interrupt",
            "citation_validate": "citation_validate",
        },
    )
    builder.add_edge("registration_interrupt", "citation_validate")
    builder.add_conditional_edges(
        "citation_validate",
        route_after_citation,
        {
            "hospital": "hospital",
            "medical": "medical",
            "save_memory": "save_memory",
        },
    )
    builder.add_edge("save_memory", END)
    return builder.compile(checkpointer=checkpointer)
