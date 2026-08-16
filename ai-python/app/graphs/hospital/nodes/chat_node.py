"""谈心聊天节点。"""

from typing import TYPE_CHECKING

from app.graphs.hospital.nodes import ai_message, invoke_reply_agent
from app.graphs.hospital.state import State

if TYPE_CHECKING:
    from app.graphs.hospital.graph import GraphDependencies


def build_chat_node(deps: "GraphDependencies"):
    def chat(state: State) -> dict:
        return {"messages": [ai_message(invoke_reply_agent(deps.chat_agent, state))]}

    return chat
