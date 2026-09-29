"""高精度规则之后，按 INTENT_BACKEND 运行 Jev 或 Ollama 分类器。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from loguru import logger

from app.core.config import get_settings
from app.graphs.hospital.state import AgentName
from app.intent.jev_classifier import get_jev_intent_classifier
from app.intent.ollama_classifier import get_ollama_intent_classifier
from app.intent.rules import detect_safety_flags, match_rules

LocalRouteStage = Literal["rules", "jev_model", "ollama_model", "llm_required"]
_CONDITIONAL_REQUEST = re.compile(
    r"如果|要是|假如|假使|倘若|若是|否则|不然|除非|不是的话|要不然|要不就|要不是"
)


@dataclass(frozen=True)
class LocalRouteResult:
    """前两级判断的标签、可信度和升级原因，供 begin_node 决定下一步。"""

    accepted: bool
    selected_agents: list[AgentName] = field(default_factory=list)
    stage: LocalRouteStage = "llm_required"
    scores: dict[str, float] = field(default_factory=dict)
    matched_rules: list[str] = field(default_factory=list)
    safety_flags: list[str] = field(default_factory=list)
    escalation_reason: str | None = None
    margin: float | None = None
    model_version: str | None = None

    def metadata(self) -> dict:
        return {
            "stage": self.stage,
            "scores": self.scores,
            "matched_rules": self.matched_rules,
            "safety_flags": self.safety_flags,
            "escalation_reason": self.escalation_reason,
            "margin": self.margin,
            "model_version": self.model_version,
            "router_version": "cascade-v3",
        }


def route_locally(text: str) -> LocalRouteResult:
    """规则优先；分类器无法确定时，交给 begin_node 的云端 LLM。"""

    safety_flags = detect_safety_flags(text)
    if _CONDITIONAL_REQUEST.search(text):
        return LocalRouteResult(
            accepted=False,
            stage="llm_required",
            safety_flags=safety_flags,
            escalation_reason="conditional_request_requires_reasoning",
        )

    rule_match = match_rules(text)
    if rule_match is not None:
        return LocalRouteResult(
            accepted=True,
            selected_agents=rule_match.selected_agents,
            stage="rules",
            matched_rules=rule_match.matched_rules,
            safety_flags=rule_match.safety_flags,
        )

    return _route_with_classifier(text, safety_flags)


def _route_with_classifier(text: str, safety_flags: list[str]) -> LocalRouteResult:
    settings = get_settings()
    backend = settings.intent_backend
    version = f"{backend}:{getattr(settings, f'intent_{backend}_model')}"
    try:
        classifier = (
            get_jev_intent_classifier()
            if backend == "jev"
            else get_ollama_intent_classifier()
        )
        prediction = classifier.predict(text)
        if backend == "jev" and prediction.reason == "jev_not_configured":
            backend = "ollama"
            version = f"ollama:{settings.intent_ollama_model}"
            logger.info("Jev API key is empty; falling back to Ollama intent classifier")
            prediction = get_ollama_intent_classifier().predict(text)
    except Exception as exc:  # noqa: BLE001 - 分类服务失败时升级到云端路由
        # 不记录请求头、响应正文或异常对象，防止 API key/患者原文进入错误日志。
        logger.warning(
            "Intent classification failed backend={} error_type={}",
            backend,
            type(exc).__name__,
        )
        return LocalRouteResult(
            accepted=False,
            safety_flags=safety_flags,
            escalation_reason=f"{backend}_unavailable",
            model_version=version,
        )

    selected = list(prediction.selected_agents) if prediction.accepted else []
    if prediction.accepted and safety_flags and "knowledge" not in selected:
        selected.insert(0, "knowledge")
    # 未通过质量门槛的标签不能成为云端失败后的兜底。
    return LocalRouteResult(
        accepted=prediction.accepted,
        selected_agents=selected,
        stage=f"{backend}_model" if prediction.accepted else "llm_required",
        scores=prediction.scores,
        safety_flags=safety_flags,
        escalation_reason=prediction.reason,
        margin=prediction.margin,
        model_version=version,
    )
