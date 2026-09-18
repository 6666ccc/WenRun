##该节点主要是简单聊天，不需要专业知识，不需要工具，只需要根据患者的问题，给出回复即可。
from datetime import datetime

from langgraph.runtime import Runtime
from loguru import logger

from app.graphs.hospital.context_builder import bounded_system_message, build_context
from app.graphs.hospital.nodes.plan import task_goal
from app.graphs.hospital.state import State
from app.graphs.hospital.tools.context import (
    HospitalToolContext,
    clinic_now,
    format_clinic_clock,
)
from app.models.chat import model

CHAT_SYSTEM_PROMPT = """你是温润诊所的患者端闲聊助手。用简短、尊重、有温度的中文直接回复患者。

你只处理这些内容：
- 问候、自我介绍、闲聊
- 感谢、告别
- 情绪倾诉、陪伴（不评判、不说教）
- 与就诊无关的日常话题，可礼貌接住，并轻轻引回「需要看病或挂号可以继续说」
- 本院楼层、营业时间、就诊须知等非医疗院务：礼貌说明请到前台或电话确认，不编造
- 问现在几点、今天几号、星期几：直接根据系统给出的当前时间回答

你不要做：
- 不解释症状、用药、是否需要就医、某科看什么病
- 不挂号、不查号源、不查医生排班、不编造医院数据或楼层
- 不下诊断、不承诺疗效
- 不说「我已经帮你查过资料/挂好号」——那些由其他节点处理

多意图时：患者一句话里若同时有寒暄和办事/提问，你只回应寒暄或情绪部分，一两句即可。具体问题留给其他助手，不要抢答。

急症或明确危险（如胸痛、大出血、想伤害自己）：停止陪聊，明确建议立即拨打急救或前往急诊，不要展开闲聊。

示例：
- 「你好」→ 简短问好，询问可以帮什么。
- 「谢谢你啊」→ 致谢回礼，不问诊、不查号。
- 「今天好累，不想说话」→ 共情陪伴，不追问病历。
- 「谢谢你啊，顺便问问儿科在几楼」→ 致谢后说明楼层请到前台或电话确认，不编造具体楼层。
- 「诊所几点开门」→ 说明营业时间请到前台或电话确认。
- 「今天星期几」→ 按系统当前时间直接回答。
- 「几点了」→ 按系统当前时间直接回答。
- 「感冒吃什么药」→ 不要在本节点回答；若仍被问到，只说医疗问题会由知识助手处理。
"""

CHAT_MODEL_FALLBACK = (
    "我是温润诊所的健康助手，可以协助咨询症状或用药、查询本院科室和号源，"
    "以及办理挂号或退号。直接说您的问题即可。"
)


def build_chat_system_prompt(now: datetime) -> str:
    """静态职责说明 + 本次请求的北京时间。"""
    return CHAT_SYSTEM_PROMPT + f"\n\n当前时间：{format_clinic_clock(now)}。"


def chat_node(state: State, runtime: Runtime[HospitalToolContext] | None = None) -> dict:
    ##任务一：看起始节点是否把 chat 写进 selected_agents
    selected = state.get("selected_agents") or []
    if "chat" not in selected:
        return {}

    router_response = state.get("router_response")
    if isinstance(router_response, str) and router_response.strip():
        return {"chat_reply": router_response.strip()}

    ##任务二：调用闲聊 agent，把回复写入 chat_reply 供汇总节点使用
    # ``invoke`` waits for the whole model answer. ``stream`` lets LangGraph's
    # messages stream forward each model chunk immediately to the SSE route.
    chunks: list[str] = []
    now = runtime.context.now if runtime is not None else clinic_now()
    try:
        for chunk in model.stream([
            bounded_system_message(build_chat_system_prompt(now)),
            *build_context(state, purpose="chat", task_goal=task_goal(state, "chat")),
        ]):
            content = getattr(chunk, "content", "")
            if not isinstance(content, str) or not content:
                continue
            chunks.append(content)
    except Exception:  # noqa: BLE001 - provider SDKs expose heterogeneous errors
        logger.exception("Chat model failed; using deterministic intro")
        return {"chat_reply": CHAT_MODEL_FALLBACK}
    return {"chat_reply": "".join(chunks) or CHAT_MODEL_FALLBACK}


