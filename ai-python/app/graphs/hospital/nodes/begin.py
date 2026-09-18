"""医院对话图的起始节点：只做意图多选，不直接回答患者。"""

from langchain_core.messages import BaseMessage, HumanMessage
from loguru import logger
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.graphs.hospital.context_builder import bounded_system_message, build_context
from app.graphs.hospital.memory import reset_turn_fields
from app.graphs.hospital.state import AgentName, State
from app.intent import LocalRouteResult, route_locally
from app.intent.metrics import record_route
from app.models.chat import model

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
  也包括患者明确要求“记住/忘掉”沟通偏好、挂号偏好或无障碍需求。
- chat：独立的寒暄、闲聊、感谢、情绪倾诉，或不要求专业知识的简短日常对话。
  也包括：本院楼层、营业时间、就诊须知等非医疗院务（礼貌引导到院咨询，不要编造）。
  也包括：问现在几点、今天几号、星期几——这是当前时间，不是本院营业时间，不要标域外。
  也包括：自我介绍（你是谁、你能做什么）。
  不包括：附着在办事、提问前的“你好”“请问”——这些不要单独加 chat。

多选规则：
- 一句话里有多件独立的事，就都选上。例如既问病情又要挂号：knowledge + tools。
- 纯办事或纯医疗提问，不要为了礼貌顺带加 chat。
- 只有社交、情绪，或非医疗院务时才选 chat。
- 问“有哪些科室 / 开了哪些科 / 能看哪些科 / 该看哪科”必须选 tools。这是实时科室目录，不要走 knowledge。
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
    messages = state.get("messages") or []
    latest = next(
        (message for message in reversed(messages) if isinstance(message, HumanMessage)),
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
            return _response_text(model.invoke(request_messages))
        except Exception:  # noqa: BLE001 - provider SDKs expose heterogeneous errors
            logger.exception("Intent classification failed attempt={}", attempt + 1)
    return None


def _repair_invalid_json(messages: list[BaseMessage], invalid_output: str) -> str | None:
    """当本地校验失败时，要求同一模型仅修正一次 JSON 输出。"""

    repair_prompt = REPAIR_SYSTEM_PROMPT.format(
        rules=BEGIN_SYSTEM_PROMPT,
        invalid_output=invalid_output[:2_000],
    )
    try:
        return _response_text(model.invoke([bounded_system_message(repair_prompt), *messages]))
    except Exception:  # noqa: BLE001 - provider SDKs expose heterogeneous errors
        logger.exception("Intent JSON repair failed")
        return None


def _route_locally(text: str) -> LocalRouteResult:
    """薄包装便于单元测试替换，同时让 begin 节点不依赖分类器实现细节。"""

    return route_locally(text)


_FOLLOWUP_AGENTS: frozenset[str] = frozenset({"tools", "knowledge"})
_FOLLOWUP_REPLY_FIELDS: tuple[str, ...] = ("tools_reply", "knowledge_reply")


def pending_followup(state: State) -> bool:
    """上一轮业务/知识助手是否在追问参数（本节点尚未重置上一轮字段，可直接读）。

    本地规则与轻量分类器只看最新一句，“明天下午”“内科”这类补充回答会被误判成闲聊；
    此时必须交给能看到历史的 LLM 路由。
    """

    previous_agents = state.get("selected_agents") or []
    if not any(agent in _FOLLOWUP_AGENTS for agent in previous_agents):
        return False
    for field in _FOLLOWUP_REPLY_FIELDS:
        reply = state.get(field)
        if isinstance(reply, str) and reply.rstrip().endswith(("？", "?")):
            return True
    return False


def begin_node(state: State) -> dict:
    """执行规则→轻量模型→LLM 的级联分类，并写入图 State。"""

    messages = build_context(state, purpose="route")
    user_text = _latest_user_text(state)
    local = _route_locally(user_text)
    route_metadata = local.metadata()
    router_fallback = False
    router_response: str | None = None
    out_of_scope = False

    # 规则命中足够可靠可以直接用；轻量模型没有上下文，追问接续时改走带历史的 LLM。
    local_accepted = local.accepted
    if local_accepted and local.stage != "rules" and pending_followup(state):
        local_accepted = False
        route_metadata["escalation_reason"] = "pending_followup"

    if local_accepted:
        selected_agents = list(local.selected_agents)
    else:
        raw_decision = _classify(messages)
        decision = _parse_decision(raw_decision or "")
        repaired = False

        # 首次输出无法通过 JSON/Pydantic 校验时，让模型按同一规则修正一次。
        if decision is None and raw_decision is not None:
            repaired_decision = _repair_invalid_json(messages, raw_decision)
            decision = _parse_decision(repaired_decision or "")
            repaired = decision is not None
            if decision is None:
                logger.warning("Intent classifier returned invalid JSON after one repair attempt")

        if decision is None:
            # LLM 不可用时，优先采用轻量模型已给出的标签，避免把能分类的请求
            # 误说成“没能判断需求”。完全没有本地线索时再给确定性澄清。
            if local.selected_agents:
                selected_agents = list(local.selected_agents)
                route_metadata["stage"] = "lightweight_degraded"
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

    # 安全信号优先级高于语义分类，不允许后续模型把医疗路径移除。
    if local.safety_flags and "knowledge" not in selected_agents:
        selected_agents.insert(0, "knowledge")

    logger.info(
        "intent_route conversation_id={} stage={} agents={} escalation_reason={} "
        "safety_flags={} scores={}",
        state.get("conversation_id"),
        route_metadata.get("stage"),
        selected_agents,
        route_metadata.get("escalation_reason"),
        route_metadata.get("safety_flags"),
        route_metadata.get("scores"),
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
