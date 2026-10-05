"""普通图的第一站：判断这句话需要哪些助手处理，不直接回答患者。

结果写入 State.selected_agents，可同时包含 knowledge（医学知识）、chat（闲聊）
和 tools（本院业务）。请从 begin_node 往下读，它按这个顺序判断，命中即停：

1. 高精度规则：句式完全明确时直接定标签（实现在 app/intent/rules.py）。
2. 多标签分类器：默认调用 TokenDance Jev SystemOne API，可配置切换为本地 Ollama。
   上一轮助手还在追问时跳过分类器结果，
   因为“明天下午”这类短句没有上文会被误判成闲聊。
3. 大模型：看得到最近几轮对话。输出格式不合格就要求重答一次；仍失败时，
   优先沿用分类器已经给出的倾向，完全没有线索再给一句固定澄清。

前两步合成一次级联判断，入口是本文件的 _route_locally，细节在 app/intent/cascade.py。
本文件后半是第三步专用的提示词和结果校验，阅读主流程时可以先跳过。
"""

import re

from langchain_core.messages import BaseMessage, HumanMessage
from loguru import logger
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.graphs.hospital.context_builder import bounded_system_message, build_context
from app.graphs.hospital.memory import reset_turn_fields
from app.graphs.hospital.state import AgentName, State
from app.intent import LocalRouteResult, route_locally
from app.intent.metrics import record_route
from app.models.chat import model as shared_model
from app.observability.agent_output import log_agent_output

model = shared_model.model_copy(update={"purpose": "route"})


def begin_node(state: State) -> dict:
    """按「规则 → Jev/Ollama 分类器 → 云端大模型」识别意图。"""
    # 按「判断意图」这个用途，从当前对话里抽出最近几轮和还没办完的事，打包成意图分类器可以看懂的上下文。
    messages = build_context(state, purpose="route")
    user_text = _latest_user_text(state)
    # 调用意图路由
    local = _route_locally(user_text)
    route_metadata = local.metadata()
    router_fallback = False
    router_response: str | None = None
    out_of_scope = False

    # 第一步命中高精度规则：直接采用，即使上一轮还在追问也不改走大模型。
    # 第二步是意图分类器。它看不到历史，追问中的短句（如“明天下午”）改走第三步。
    local_accepted = local.accepted
    if local_accepted and local.stage != "rules" and pending_followup(state):
        local_accepted = False
        route_metadata["escalation_reason"] = "pending_followup"

    if local_accepted:
        selected_agents = list(local.selected_agents)
    else:
        # 第三步：大模型结合最近对话分类；格式见本文件后半的 IntentDecision。
        raw_decision = _classify(messages)
        decision = _parse_decision(raw_decision or "")
        repaired = False

        if decision is None and raw_decision is not None:
            repaired_decision = _repair_invalid_json(messages, raw_decision)
            decision = _parse_decision(repaired_decision or "")
            repaired = decision is not None
            if decision is None:
                logger.warning(
                    "Intent classifier returned invalid JSON after one repair attempt"
                )

        if decision is None:
            if local.selected_agents:
                selected_agents = list(local.selected_agents)
                route_metadata["stage"] = local.stage.replace("_model", "_degraded")
                route_metadata["fallback_reason"] = "llm_unavailable_use_local"
            else:
                selected_agents = ["chat"]
                router_fallback = True
                router_response = (
                    "抱歉，我暂时没能准确判断您的需求。您可以明确说“咨询症状或用药”、"
                    "“查询科室或号源”，或者“办理挂号或退号”。"
                )
                route_metadata["stage"] = "fallback"
                route_metadata["fallback_reason"] = "llm_unavailable_or_invalid"
        elif decision.out_of_scope:
            selected_agents = ["chat"]
            out_of_scope = True
            router_response = (
                "这个问题超出了当前健康助手的服务范围。"
                "我可以协助健康知识咨询、查询本院科室和号源，以及办理挂号或退号。"
            )
            route_metadata["stage"] = "llm"
            route_metadata["out_of_scope"] = True
            route_metadata["llm_repaired"] = repaired
        else:
            selected_agents = _normalize_agents(decision)
            route_metadata["stage"] = "llm"
            route_metadata["llm_repaired"] = repaired

    # 紧急风险（呼吸困难、胸痛等）必须带上医学知识助手，后面的分类不能把它拿掉。
    if local.safety_flags and "knowledge" not in selected_agents:
        selected_agents.insert(0, "knowledge")

    # Clinical requests remain on knowledge even when the patient says “记住”.
    from app.graphs.hospital.nodes.knowledge import necessary_clinical_scopes

    if necessary_clinical_scopes(user_text):
        if re.search(r"挂号|预约|号源|排班|退号|科室|医生", user_text):
            if "knowledge" not in selected_agents:
                selected_agents.insert(0, "knowledge")
        else:
            selected_agents = ["knowledge"]
        router_fallback = out_of_scope = False
        router_response = None
        route_metadata["clinical_profile_route_guard"] = True

    logger.info(
        "意图路由完成 会话={} 阶段={} 选中助手={} 升级原因={} 命中规则={} "
        "安全标记={} 标签分数={} | intent_route",
        state.get("conversation_id"),
        _describe_route_code(route_metadata.get("stage"), _ROUTE_STAGE_LABELS),
        [
            f"{_AGENT_LABELS_ZH.get(agent, agent)}（{agent}）"
            for agent in selected_agents
        ],
        _describe_route_code(
            route_metadata.get("escalation_reason"), _ESCALATION_REASON_LABELS
        ),
        _describe_route_codes(route_metadata.get("matched_rules"), _RULE_LABELS),
        _describe_route_codes(route_metadata.get("safety_flags"), _SAFETY_LABELS),
        _describe_intent_scores(route_metadata.get("scores") or {}),
    )
    record_route(
        route_metadata,
        fallback=router_fallback,
        out_of_scope=out_of_scope,
    )
    return {
        **reset_turn_fields(),
        "selected_agents": selected_agents,
        "intent_route": route_metadata,
        "router_fallback": router_fallback,
        "router_response": router_response,
    }


def _route_locally(text: str) -> LocalRouteResult:
    """把患者最新那句话交给 app/intent/cascade.py：先用高精度规则判断；
    规则没命中，再跑选定的意图分类器。两步都拿不准时走云端大模型。"""
    return route_locally(text)


_FOLLOWUP_AGENTS: frozenset[str] = frozenset({"tools", "knowledge"})
_FOLLOWUP_REPLY_FIELDS: tuple[str, ...] = ("tools_reply", "knowledge_reply")
_AGENT_LABELS_ZH = {
    "knowledge": "医疗知识助手",
    "chat": "闲聊助手",
    "tools": "医院业务助手",
}
_INTENT_LABELS_ZH = {"knowledge": "医疗知识", "chat": "闲聊", "tools": "医院业务"}
_ROUTE_STAGE_LABELS = {
    "rules": "规则直接命中",
    "jev_model": "Jev 意图判断",
    "jev_degraded": "云端不可用，采用 Jev 已接受结果",
    "ollama_degraded": "云端不可用，采用 Ollama 已接受结果",
    "ollama_model": "本地 Ollama 判断",
    "llm_required": "需要云端大模型判断",
    "llm": "云端大模型已判断",
    "fallback": "进入固定澄清兜底",
}
_ESCALATION_REASON_LABELS = {
    "conditional_request_requires_reasoning": "包含条件判断，交给云端大模型",
    "pending_followup": "正在回答上一轮追问，交给云端大模型结合历史判断",
    "jev_not_configured": "Jev API key 尚未配置",
    "jev_unavailable": "Jev 服务不可用",
    "ollama_unavailable": "本地 Ollama 不可用",
    "invalid_output": "意图分类器输出格式无效",
    "low_confidence": "意图分类器判断信心不足",
    "ambiguous_top_intents": "意图分类器无法区分最可能的意图",
    "local_uncertain": "意图分类器标记为不确定",
    "local_out_of_scope": "意图分类器认为问题超出服务范围",
}
_RULE_LABELS = {
    "appointment_action": "挂号或退号办理请求",
    "realtime_business": "号源、排班或预约查询",
    "department_catalog": "本院科室目录查询",
    "explicit_medical_question": "明确的医疗知识问题",
    "medical_context_with_business": "医疗问题与院内业务并存",
    "department_recommendation": "就诊科室建议",
    "urgent_safety": "急症或安全风险信号",
    "hospital_static_information": "医院静态信息查询",
    "exact_social": "简短寒暄或感谢",
    "exact_identity": "助手身份问题",
    "exact_clock_question": "当前时间问题",
    "identity_with_other_intents": "身份问题与其他意图并存",
}
_SAFETY_LABELS = {
    "breathing_difficulty": "呼吸困难",
    "severe_bleeding": "严重出血",
    "loss_of_consciousness": "意识丧失",
    "possible_stroke": "疑似卒中信号",
    "self_harm": "自伤风险",
    "acute_chest_pain": "急性胸痛",
}


def _describe_route_codes(
    values: list[str] | None, labels: dict[str, str]
) -> list[str]:
    return [f"{labels.get(value, value)}（{value}）" for value in values or []]


def _describe_route_code(value: str | None, labels: dict[str, str]) -> str | None:
    if value is None:
        return None
    return f"{labels.get(value, value)}（{value}）"


def _describe_intent_scores(scores: dict[str, float]) -> dict[str, float]:
    return {
        f"{_INTENT_LABELS_ZH.get(label, label)}（{label}）": score
        for label, score in scores.items()
    }


def pending_followup(state: State) -> bool:
    """上一轮医学或挂号助手是否还在追问（日期、科室、医生等）。

    本节点清空上一轮回复之前调用。追问还在进行时，第二步分类器不可信，
    必须交给能看到历史的第三步。
    """

    previous_agents = state.get("selected_agents") or []
    if not any(agent in _FOLLOWUP_AGENTS for agent in previous_agents):
        return False
    for field in _FOLLOWUP_REPLY_FIELDS:
        reply = state.get(field)
        if isinstance(reply, str) and reply.rstrip().endswith(("？", "?")):
            return True
    return False


# ---------------------------------------------------------------------------
# 第三步专用：提示词，以及大模型返回结果的格式约束。
# 前两步不经过这里。
# ---------------------------------------------------------------------------

BEGIN_SYSTEM_PROMPT = """你是温润诊所患者端的意图路由器，不是对患者说话的助手。
结合提供的短期会话上下文，根据患者【最新一条消息】判断要启动哪些内部 Agent。
历史消息只用于理解省略和指代，不能把旧意图重复算入本轮。只分类，不要解释病情，不要回答问题，不要打招呼。

可选标签（可多选，至少选 1 个）：
- knowledge：只处理医疗知识，不处理本院事务。
  包括：症状、疾病、用药、护理、是否需要就医、检查前后医学注意、某科看什么病。
  不包括：楼层、营业时间、就诊须知、科室目录、号源、排班、挂号。
- tools：需要本院实时业务数据，或患者要办挂号、退号这类院内业务。
  包括：本院当前开设了哪些科室、查号源、查某位医生或某天排班、查我的预约，
  以及“帮我挂号”“我要退号”这类办理请求（由业务 Agent 查清号源并引导患者完成）。
- chat：独立的寒暄、闲聊、感谢、情绪倾诉，或不要求专业知识的简短日常对话。
  也包括：本院楼层、营业时间、就诊须知等非医疗院务（礼貌引导到院咨询，不要编造）。
  也包括：问现在几点、今天几号、星期几——这是当前时间，不是本院营业时间，不要标域外。
  也包括：自我介绍（你是谁、你能做什么）。
  不包括：附着在办事、提问前的“你好”“请问”——这些不要单独加 chat。

多选规则：
- 一句话里有多件独立的事，就都选上。例如既问病情又要挂号：knowledge + tools。
- 条件句的每个分支都要选上，不要先替患者判断条件成不成立。
  例如“是周五就挂号，不是就讲骨折怎么办，我好害怕”同时选 chat、knowledge、tools。
- 纯办事或纯医疗提问，不要为了礼貌顺带加 chat。
- 只有社交、情绪，或非医疗院务时才选 chat。
- 问“有哪些科室 / 开了哪些科 / 能看哪些科”必须选 tools。这是实时科室目录，不要走 knowledge。
- 问“该看哪科”同时选 knowledge 和 tools：需要医疗分科判断，也需要本院实时科室目录。
- 问某科看什么病选 knowledge；问该科在几楼、几点开门选 chat。不要因为出现“内科”“儿科”就选 tools。
- “我想看内科”：要挂号或找号选 tools；问内科看什么病选 knowledge；两者都有就都选。
- 如果用户明确要求处理编程、金融、法律、购物、旅游、通用知识等与医院服务和
  健康陪伴无关的任务，selected_agents 输出空数组，out_of_scope 输出 true。
- 模糊但仍可能和医院或健康有关时不能标记域外，按最接近的标签选择或交由澄清。
- 患者说“联网搜索/搜一下”只是检索方式，仍按问题本身分类：医疗知识走 knowledge。
- 追问接续：如果上一条助手消息在追问日期、时段、科室、医生、退哪一张号等参数，而患者本条只是在补充回答
  （如“明天下午”“内科”“李雷医生”“第一个”），沿用上一轮正在办理的标签（通常是 tools），不要当成寒暄归到 chat。

示例：
- “你好” → chat
- “你是谁” → chat
- “几点了” → chat
- “今天星期几” → chat
- “感冒吃什么药” → knowledge
- “感冒有哪些症状” → knowledge
- “联网搜索一下感冒的症状” → knowledge
- “你们医院有哪些科室” → tools
- “现在能看哪些科” → tools
- “帮我挂号” → tools
- “张医生下周还有号吗” → tools
- “儿科在几楼” → chat
- “诊所几点开门” → chat
- “感冒了该看哪科” → knowledge, tools
- “帮我挂明天内科，另外感冒要不要来医院？” → knowledge, tools
- “今天是周几？是周五请帮我挂骨科，不是的话讲讲骨折怎么办。我好害怕。” → chat, knowledge, tools
- “谢谢你啊，顺便问问儿科在几楼。” → chat
- “你好，帮我挂内科” → tools
- 上一条助手：“请问您想约哪一天？” 患者：“明天下午” → tools
- “帮我写一个排序算法” → out_of_scope=true, selected_agents=[]

输出要求：
- 只返回一个 JSON 对象，不要 Markdown 代码块、解释或其他文字。
- JSON 必须只有 selected_agents 和 out_of_scope 两个字段。
- 正确格式示例：{"selected_agents":["knowledge","tools"],"out_of_scope":false}
"""

REPAIR_SYSTEM_PROMPT = """你刚才的意图分类结果不符合要求。请基于下面的分类规则和患者消息重新输出。

{rules}

上一次无效输出如下：
{invalid_output}

这一次只返回一个可被 JSON 解析、且符合指定字段与标签约束的 JSON 对象；不要 Markdown、解释或任何额外文字。
"""


class IntentDecision(BaseModel):
    """路由模型的本地校验结构，不会作为工具强制模型调用。"""

    model_config = ConfigDict(extra="forbid")

    selected_agents: list[AgentName] = Field(
        default_factory=list,
        description="可多选，且只能从 knowledge / chat / tools 中选择。",
    )
    out_of_scope: bool = False

    @model_validator(mode="after")
    def validate_scope(self) -> "IntentDecision":
        if self.out_of_scope and self.selected_agents:
            raise ValueError("out_of_scope=true 时不能同时选择内部 Agent")
        if not self.out_of_scope and not self.selected_agents:
            raise ValueError("域内请求至少选择一个内部 Agent")
        return self


def _normalize_agents(decision: IntentDecision | None) -> list[AgentName]:
    """去重并做最终兜底，保证图状态始终得到合法的标签列表。"""

    if decision is None:
        return ["chat"]

    selected: list[AgentName] = []
    for name in decision.selected_agents:
        if name not in selected:
            selected.append(name)
    return selected or ["chat"]


def _latest_user_text(state: State) -> str:
    """该函数主要是获取最新一条患者消息，作为意图路由的输入。为什么只获取最新一条？
    因为意图路由的输入不能包含历史消息，否则会导致模型混淆。
    """
    messages = state.get("messages") or []
    latest = next(
        (
            message
            for message in reversed(messages)
            if isinstance(message, HumanMessage)
        ),
        None,
    )
    content = getattr(latest, "content", "")
    return content if isinstance(content, str) else ""


def _response_text(response: object) -> str:
    """兼容 LangChain 消息对象，安全地取出模型最终文本。"""

    content = getattr(response, "content", "")
    if isinstance(content, str):
        return content.strip()
    return ""


def _parse_decision(text: str) -> IntentDecision | None:
    """使用 Pydantic 校验模型输出；格式或字段不合法时返回 None。"""

    if not text:
        return None

    try:
        return IntentDecision.model_validate_json(text)
    except ValidationError:
        return None


def _classify(messages: list[BaseMessage]) -> str | None:
    """让模型自主做一次分类；调用失败时仅重试一次相同请求。"""

    request_messages = [bounded_system_message(BEGIN_SYSTEM_PROMPT), *messages]
    for attempt in range(2):
        try:
            output = _response_text(model.invoke(request_messages))
            log_agent_output("intent_router", output, phase="classification")
            return output
        except Exception:  # noqa: BLE001 - provider SDKs expose heterogeneous errors
            logger.exception("Intent classification failed attempt={}", attempt + 1)
    return None


def _repair_invalid_json(
    messages: list[BaseMessage], invalid_output: str
) -> str | None:
    """当本地校验失败时，要求同一模型仅修正一次 JSON 输出。"""

    repair_prompt = REPAIR_SYSTEM_PROMPT.format(
        rules=BEGIN_SYSTEM_PROMPT,
        invalid_output=invalid_output[:2_000],
    )
    try:
        output = _response_text(
            model.invoke([bounded_system_message(repair_prompt), *messages])
        )
        log_agent_output("intent_router", output, phase="json_repair")
        return output
    except Exception:  # noqa: BLE001 - provider SDKs expose heterogeneous errors
        logger.exception("Intent JSON repair failed")
        return None
