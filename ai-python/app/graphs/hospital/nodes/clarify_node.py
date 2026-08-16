"""含糊意图澄清节点。"""

from typing import TYPE_CHECKING

from app.graphs.hospital.nodes import ai_message, invoke_reply_agent
from app.graphs.hospital.state import State

if TYPE_CHECKING:
    from app.graphs.hospital.graph import GraphDependencies

DEFAULT_CLARIFY_REPLY = (
    "我想确认一下：您是想闲聊、了解医院信息或办事，还是咨询健康科普呢？"
)


def build_clarify_node(deps: "GraphDependencies"):
    def clarify(state: State) -> dict:
        if deps.clarify_agent is None:
            return {"messages": [ai_message(DEFAULT_CLARIFY_REPLY)]}
        return {"messages": [ai_message(invoke_reply_agent(deps.clarify_agent, state))]}

    return clarify
