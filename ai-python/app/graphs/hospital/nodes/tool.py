##该节点处理本院实时业务查询，需要挂载工具；委托令牌与当前时间通过运行时上下文注入。
from datetime import datetime

from app.graphs.hospital.memory import recent_messages
from app.graphs.hospital.state import State
from app.graphs.hospital.tools import (
    HospitalToolContext,
    cancel_registration,
    create_registration,
    list_departments,
    list_doctors,
    list_my_registrations,
    list_schedules,
)
from app.graphs.hospital.tools.context import format_clinic_clock
from app.models.chat import model
from langchain.agents import create_agent
from langchain.agents.middleware import ModelRequest, dynamic_prompt
from langgraph.runtime import Runtime
from loguru import logger

TOOL_SYSTEM_PROMPT = """你是温润诊所的患者端业务助手。用简短、尊重、有温度的中文直接回复患者。

工作流程（必须按顺序，不要跳步）：
1. 需要本院实时业务数据时，先调用工具，再根据工具返回的内容回答。
2. 按问题选择工具：
   - 有哪些科室、开了哪些科、能看哪些科 → list_departments
   - 某科有哪些医生、有没有某位医生 → list_doctors
   - 某科或某位医生的排班、某天有没有号、余号多少 → list_schedules
   - 我挂了什么号、我的预约、我的号退了没 → list_my_registrations
3. 一个问题需要多项数据时，可以连续调用多个工具，全部拿到后再统一回答。
4. 只根据工具结果陈述事实，不补充自己的假设，不把工具没返回的日期说成「今天/明天」。
5. 患者要挂号、改约或退号时：先用 list_schedules 查清可选号源，或用 list_my_registrations 查清本人现有预约，
   把结果清楚列给患者，再说明最后一步需要他自己在挂号页面确认。不要说自己已经挂上或已经退掉。
6. 工具返回「暂时无法查询」或提示姓名、科室不对时，如实转达并请患者确认或稍后重试，不要编造数据。

工具参数：
- 科室、医生用患者的说法即可，例如 department="内科"、doctor="张伟"。
- 日期：系统提示里有当前北京时间。调用 list_schedules 时可把「今天 / 明天 / 这周五」换成 YYYY-MM-DD，也可以直接传「今天」「明天」。
- 问今天几号、星期几：直接根据系统给出的当前时间回答，不必调用工具。
- list_my_registrations 只会返回当前登录患者本人的记录，你无法也不要尝试查询他人。

你不要做：
- 不直接提交挂号、退号、改期，也不改排班；你只负责查清信息并引导，最终确认由患者在挂号页面完成
- 不解释症状、用药、是否需要就医，也不说某科通常看什么病
- 不闲聊、不陪聊
- 不编造科室名、医生、号源、时间、费用或链接
- 余号为 0 时如实说明已约满，不要暗示还能加号

多意图时：患者一句话里若同时有业务查询和医疗提问/寒暄，你只回答业务查询部分，其余留给其他助手。
"""

WRITE_TOOL_SYSTEM_PROMPT = """你是温润诊所的患者端业务助手。用简短、尊重、有温度的中文直接回复患者。

工作流程（必须按顺序，不要跳步）：
1. 需要本院实时业务数据时，先调用工具，再根据工具返回的内容回答。
2. 按问题选择工具：
   - 有哪些科室、开了哪些科、能看哪些科 → list_departments
   - 某科有哪些医生、有没有某位医生 → list_doctors
   - 某科或某位医生的排班、某天有没有号、余号多少 → list_schedules
   - 我挂了什么号、我的预约、我的号退了没 → list_my_registrations
3. 一个问题需要多项数据时，可以连续调用多个工具，全部拿到后再统一回答。
4. 只根据工具结果陈述事实，不补充自己的假设，不把工具没返回的日期说成「今天/明天」。
5. 患者要挂号时：先用 list_schedules 查到确切的排班，拿到它的 id，再调用 create_registration 并把这个 id 传进去。
   排班 id 必须来自工具返回，绝对不能猜、不能凭印象填。
   患者的说法对应多个可选号源时，先把可选项列出来问清楚要哪一个，再提交。
6. 患者要退号时：先用 list_my_registrations 查到那张挂号单，拿到它的 id，再调用 cancel_registration。
   患者名下有多张有效挂号单时，先列出来问清楚退哪一张，再提交。
7. create_registration 和 cancel_registration 会先把一张确认卡片交给患者，由患者本人点确认。
   卡片由系统渲染，你不需要复述卡片内容，也不要在患者确认之前说已经挂上或已经退掉。
   工具返回结果后，如实转达成功或失败的原因。
8. 工具返回「暂时无法查询」或提示姓名、科室不对时，如实转达并请患者确认或稍后重试，不要编造数据。

工具参数：
- 科室、医生用患者的说法即可，例如 department="内科"、doctor="张伟"。
- 日期：系统提示里有当前北京时间。调用 list_schedules 时可把「今天 / 明天 / 这周五」换成 YYYY-MM-DD，也可以直接传「今天」「明天」。
- 问今天几号、星期几：直接根据系统给出的当前时间回答，不必调用工具。
- list_my_registrations 只会返回当前登录患者本人的记录，你无法也不要尝试查询他人。

你不要做：
- 不改排班、不调号源总量、不替他人挂号或退号
- 不解释症状、用药、是否需要就医，也不说某科通常看什么病
- 不闲聊、不陪聊
- 不编造科室名、医生、号源、时间、费用或链接
- 余号为 0 时如实说明已约满，不要暗示还能加号

多意图时：患者一句话里若同时有业务查询和医疗提问/寒暄，你只回答业务查询部分，其余留给其他助手。
"""


def build_tool_system_prompt(now: datetime) -> str:
    """静态职责说明 + 本次请求的北京时间。"""
    return TOOL_SYSTEM_PROMPT + f"\n\n当前时间：{format_clinic_clock(now)}。"


def build_write_tool_system_prompt(now: datetime) -> str:
    """可写会话的职责说明 + 本次请求的北京时间。"""
    return WRITE_TOOL_SYSTEM_PROMPT + f"\n\n当前时间：{format_clinic_clock(now)}。"


@dynamic_prompt
def hospital_tool_prompt(request: ModelRequest) -> str:
    return build_tool_system_prompt(request.runtime.context.now)


@dynamic_prompt
def hospital_write_tool_prompt(request: ModelRequest) -> str:
    return build_write_tool_system_prompt(request.runtime.context.now)


HOSPITAL_TOOLS = [
    list_departments,
    list_doctors,
    list_schedules,
    list_my_registrations,
]

HOSPITAL_WRITE_TOOLS = [
    create_registration,
    cancel_registration,
]

agent = create_agent(
    model=model,
    tools=HOSPITAL_TOOLS,
    context_schema=HospitalToolContext,
    middleware=[hospital_tool_prompt],
)

# 写工具靠 interrupt() 暂停等患者确认，而 interrupt 需要 checkpointer 才能恢复。
# 没有 checkpointer 时它不会报错，只会静默地什么都不做，所以这个 Agent 只在
# runtime context 明确开启写能力时才使用。
writable_agent = create_agent(
    model=model,
    tools=HOSPITAL_TOOLS + HOSPITAL_WRITE_TOOLS,
    context_schema=HospitalToolContext,
    middleware=[hospital_write_tool_prompt],
)


def tool_node(state: State, runtime: Runtime[HospitalToolContext]) -> dict:
    ##任务一：看起始节点是否把 tools 写进 selected_agents
    selected = state.get("selected_agents") or []
    if "tools" not in selected:
        return {}

    ##任务二：没有委托令牌就不要打扰模型，直接给出降级回复
    context = runtime.context
    delegated_token = getattr(context, "delegated_token", "")
    if not isinstance(delegated_token, str) or not delegated_token.strip():
        logger.error(
            "tool_node_missing_delegated_token conversation_id={}",
            state.get("conversation_id"),
        )
        return {"tools_reply": "业务查询服务暂不可用，请稍后重试。"}

    ##任务三：运行时上下文只在本次请求内有效，直接透传给嵌套 Agent
    selected = writable_agent if getattr(context, "writes_enabled", False) else agent
    result = selected.invoke(
        {"messages": recent_messages(state)},
        context=context,
    )
    messages = result.get("messages") or []
    last = messages[-1] if messages else None
    content = getattr(last, "content", "") if last is not None else ""
    if not isinstance(content, str):
        content = str(content)
    return {"tools_reply": content}
