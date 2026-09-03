"""医院对话图的起始节点：只做意图多选，不直接回答患者。"""

from app.graphs.hospital.memory import recent_messages, reset_turn_fields
from app.graphs.hospital.state import AgentName, State
from app.models.chat import model
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from loguru import logger
from pydantic import BaseModel, ConfigDict, Field, ValidationError

DEPARTMENT_LIST_KEYWORDS = (
    "哪些科室",
    "有哪些科",
    "什么科室",
    "开设了哪些",
    "有什么科",
    "哪些科",
    "哪个科室",
    "看哪科",
    "看什么科",
)
MEDICAL_CONTEXT_KEYWORDS = (
    "感冒",
    "发烧",
    "咳嗽",
    "疼",
    "痛",
    "药",
    "症状",
    "不舒服",
    "难受",
)

BEGIN_SYSTEM_PROMPT = """你是温润诊所患者端的意图路由器，不是对患者说话的助手。
根据患者【最新一条消息】判断要启动哪些内部 Agent。只分类，不要解释病情，不要回答问题，不要打招呼。

可选标签（可多选，至少选 1 个）：
- knowledge：只处理医疗知识，不处理本院事务。
  包括：症状、疾病、用药、护理、是否需要就医、检查前后医学注意、某科看什么病。
  不包括：楼层、营业时间、就诊须知、科室目录、号源、排班、挂号。
- tools：需要本院实时业务数据，或患者要办挂号、退号这类院内业务。
  包括：本院当前开设了哪些科室、查号源、查某位医生或某天排班、查我的预约，
  以及“帮我挂号”“我要退号”这类办理请求（由业务 Agent 查清号源并引导患者完成）。
- chat：独立的寒暄、闲聊、感谢、情绪倾诉，或与就诊、医疗都无关的对话。
  也包括：本院楼层、营业时间、就诊须知等非医疗院务（礼貌引导到院咨询，不要编造）。
  不包括：附着在办事、提问前的“你好”“请问”——这些不要单独加 chat。

多选规则：
- 一句话里有多件独立的事，就都选上。例如既问病情又要挂号：knowledge + tools。
- 纯办事或纯医疗提问，不要为了礼貌顺带加 chat。
- 只有社交、情绪，或非医疗院务时才选 chat。
- 问“有哪些科室 / 开了哪些科 / 能看哪些科 / 该看哪科”必须选 tools。这是实时科室目录，不要走 knowledge。
- 问某科看什么病选 knowledge；问该科在几楼、几点开门选 chat。不要因为出现“内科”“儿科”就选 tools。
- “我想看内科”：要挂号或找号选 tools；问内科看什么病选 knowledge；两者都有就都选。
- 三个都不像时，只选 chat。不要发明第四个标签。

示例：
- “你好” → chat
- “感冒吃什么药” → knowledge
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

输出要求：
- 只返回一个 JSON 对象，不要 Markdown 代码块、解释或其他文字。
- JSON 必须只有 selected_agents 字段，字段值为标签数组。
- 正确格式示例：{"selected_agents":["knowledge","tools"]}
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
        min_length=1,
        description="可多选，且只能从 knowledge / chat / tools 中选择。",
    )


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


def _is_department_list_query(text: str) -> bool:
    return any(keyword in text for keyword in DEPARTMENT_LIST_KEYWORDS)


def _has_medical_context(text: str) -> bool:
    return any(keyword in text for keyword in MEDICAL_CONTEXT_KEYWORDS)


def _apply_department_tool_guard(selected: list[AgentName], user_text: str) -> list[AgentName]:
    """科室目录问句必须走 tools；纯目录不再并行 knowledge，避免网页检索污染最终回复。"""

    if not _is_department_list_query(user_text):
        return selected

    guarded = list(selected)
    if "tools" not in guarded:
        guarded.append("tools")
    if not _has_medical_context(user_text):
        guarded = [name for name in guarded if name not in {"knowledge", "chat"}]
    return guarded or ["tools"]


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

    request_messages = [SystemMessage(content=BEGIN_SYSTEM_PROMPT), *messages]
    for attempt in range(2):
        try:
            return _response_text(model.invoke(request_messages))
        except Exception:
            logger.exception("Intent classification failed attempt={}", attempt + 1)
    return None


def _repair_invalid_json(messages: list[BaseMessage], invalid_output: str) -> str | None:
    """当本地校验失败时，要求同一模型仅修正一次 JSON 输出。"""

    repair_prompt = REPAIR_SYSTEM_PROMPT.format(
        rules=BEGIN_SYSTEM_PROMPT,
        invalid_output=invalid_output[:2_000],
    )
    try:
        return _response_text(model.invoke([SystemMessage(content=repair_prompt), *messages]))
    except Exception:
        logger.exception("Intent JSON repair failed")
        return None


def begin_node(state: State) -> dict:
    """调用模型分类，并将通过 Pydantic 校验的结果写入图 State。"""

    messages = recent_messages(state)
    raw_decision = _classify(messages)
    decision = _parse_decision(raw_decision or "")

    # 首次输出无法通过 JSON/Pydantic 校验时，让模型按同一规则修正一次。
    if decision is None and raw_decision is not None:
        repaired_decision = _repair_invalid_json(messages, raw_decision)
        decision = _parse_decision(repaired_decision or "")
        if decision is None:
            logger.warning("Intent classifier returned invalid JSON after one repair attempt")

    selected_agents = _apply_department_tool_guard(
        _normalize_agents(decision),
        _latest_user_text(state),
    )
    logger.info(
        "intent_selected_agents conversation_id={} agents={}",
        state.get("conversation_id"),
        selected_agents,
    )
    return {**reset_turn_fields(), "selected_agents": selected_agents}
