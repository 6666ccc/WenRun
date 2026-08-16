"""意图判断节点：只分类，不产生面向患者的答案。"""

from typing import TYPE_CHECKING, Any

from pydantic import ValidationError

from app.graphs.hospital.nodes import VALID_INTENTS
from app.graphs.hospital.state import State
from app.models.intent_result import IntentResult

_CLASSIFICATION_ERRORS = (ValidationError, ValueError, TypeError)

if TYPE_CHECKING:
    from app.graphs.hospital.graph import GraphDependencies


def build_intent_judgment_node(deps: "GraphDependencies"):
    def intent_judgment(state: State) -> dict:
        try:
            result = deps.intent_agent.invoke({"messages": state.get("messages", [])})
        except _CLASSIFICATION_ERRORS:
            return {"intent": None}
        intent = _extract_intent(result)
        if intent not in VALID_INTENTS:
            return {"intent": None}
        return {"intent": intent}

    return intent_judgment


def _extract_intent(result: Any) -> str | None:
    if result is None:
        return None
    if isinstance(result, IntentResult):
        return result.intent
    if isinstance(result, str):
        return result if result in VALID_INTENTS else None
    if isinstance(result, dict):
        if "structured_response" in result:
            return _extract_intent(result["structured_response"])
        intent = result.get("intent")
        return intent if intent in VALID_INTENTS else None
    intent = getattr(result, "intent", None)
    return intent if intent in VALID_INTENTS else None
