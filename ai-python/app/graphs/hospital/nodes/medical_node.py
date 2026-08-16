"""医疗知识节点：仅检索医疗知识库，并将片段编号为 [S1]。"""

from typing import TYPE_CHECKING

from app.graphs.hospital.nodes import ai_message, invoke_reply_agent
from app.graphs.hospital.nodes.retrieval import last_user_text, retrieve_for_node
from app.graphs.hospital.state import State
from app.rag.collections import KnowledgeBase
from app.rag.rag import chunks_to_sources, format_source_context

if TYPE_CHECKING:
    from app.graphs.hospital.graph import GraphDependencies

EMERGENCY_TOKENS = ("胸痛", "呼吸困难", "意识障碍", "意识异常", "大量出血")
BOUNDARY_TOKENS = ("诊断", "开药", "处方")
CONSERVATIVE_ANSWER = "知识库中没有足够依据回答该问题，建议咨询医生或换一种问法。"
EMERGENCY_ANSWER = "出现胸痛、呼吸困难或意识异常时，请立即前往急诊或呼叫急救，不要延误。"
BOUNDARY_ANSWER = (
    "我没有诊断和开药的权限。知识库中没有足够依据回答该问题，建议咨询医生或换一种问法。"
)


def build_medical_node(deps: "GraphDependencies"):
    def medical(state: State) -> dict:
        query = last_user_text(state)
        chunks = retrieve_for_node(deps.medical_retriever, KnowledgeBase.MEDICAL, state)
        sources = chunks_to_sources(chunks, KnowledgeBase.MEDICAL)
        if _is_emergency(query):
            update = {
                "messages": [ai_message(EMERGENCY_ANSWER)],
                "needs_rewrite": False,
            }
            if sources:
                update["sources"] = sources
            return update
        if not sources:
            answer = BOUNDARY_ANSWER if _is_boundary(query) else CONSERVATIVE_ANSWER
            return {
                "messages": [ai_message(answer)],
                "sources": [],
                "needs_rewrite": False,
            }
        agent_state = _with_source_context(state, sources)
        reply = invoke_reply_agent(deps.medical_agent, agent_state)
        return {
            "messages": [ai_message(reply)],
            "sources": sources,
            "needs_rewrite": False,
        }

    return medical


def _is_emergency(text: str) -> bool:
    return any(token in (text or "") for token in EMERGENCY_TOKENS)


def _is_boundary(text: str) -> bool:
    return any(token in (text or "") for token in BOUNDARY_TOKENS)


def _with_source_context(state: State, sources: list[dict]) -> dict:
    messages = list(state.get("messages") or [])
    messages.append({"role": "system", "content": format_source_context(sources)})
    return {**state, "messages": messages}
