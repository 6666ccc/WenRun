"""汇总各业务节点的回复，生成唯一一条面向患者的最终回复。"""

from app.graphs.hospital.state import State
from app.models.chat import model
from langchain.agents import create_agent
from langchain_core.messages import AIMessage, HumanMessage
from loguru import logger

FINAL_SYSTEM_PROMPT = """你是温润诊所患者端的回复汇总助手。
你的任务是把多个内部助手已经生成的内容整理成一条自然、简洁、连贯的中文回复。

必须遵守：
- 只能整理输入中已有的信息，不补充医学知识，不猜测医院数据，不新增诊断、药名、剂量或承诺。
- 不改变工具执行结果、预约状态、医生、科室、日期、时间、编号、金额等事实。
- 保留原文中的风险提醒、就医建议、引用编号、来源标题和完整链接，不伪造或删除来源。
- 合并重复表达，去掉“由其他助手处理”等内部协作话术。
- 不提及内部 Agent、节点、State、工具调用或汇总过程。
- 直接输出最终回复，不要添加“汇总如下”等开场白。
"""

final_agent = create_agent(
    model=model,
    tools=[],
    system_prompt=FINAL_SYSTEM_PROMPT,
)

_REPLY_FIELDS = (
    ("知识咨询", "knowledge_reply"),
    ("日常交流", "chat_reply"),
    ("业务办理", "tools_reply"),
)


def _collect_replies(state: State) -> list[tuple[str, str]]:
    """按固定顺序收集各业务节点产生的非空回复。"""
    replies: list[tuple[str, str]] = []
    for label, field in _REPLY_FIELDS:
        value = state.get(field)
        if isinstance(value, str) and value.strip():
            replies.append((label, value.strip()))
    return replies


def _join_replies(replies: list[tuple[str, str]]) -> str:
    """在模型不可用时，确定性地拼接已有回复。"""
    return "\n\n".join(reply for _, reply in replies)


def _summarize_replies(replies: list[tuple[str, str]]) -> str:
    section_blocks: list[str] = []
    for label, reply in replies:
        section_blocks.append(f"【{label}】\n{reply}")

    sections = "\n\n".join(section_blocks)
    result = final_agent.invoke(
        {
            "messages": [
                HumanMessage(
                    content=(
                        "请将以下内部回复整理成一条面向患者的最终回复。"
                        "严格保留其中的事实、风险提醒和引用来源：\n\n"
                        f"{sections}"
                    )
                )
            ]
        }
    )
    messages = result.get("messages") or []
    last_message = messages[-1] if messages else None
    content = getattr(last_message, "content", "")
    return content.strip() if isinstance(content, str) else ""


def final_node(state: State) -> dict:
    """生成最终回复，并将其作为唯一可见的 AI 消息写回图状态。"""
    replies = _collect_replies(state)

    if not replies:
        final_reply = "抱歉，暂时没有生成可用的回复，请重新描述您的问题。"
    elif len(replies) == 1:
        # 单个节点的结果无需再次调用模型，避免改写事实或引用。
        final_reply = replies[0][1]
    else:
        try:
            final_reply = _summarize_replies(replies)
        except Exception:  
            logger.exception("Final reply summarization failed")
            final_reply = ""

        if not final_reply:
            final_reply = _join_replies(replies)

    return {
        "final_reply": final_reply,
        "messages": [AIMessage(content=final_reply)],
    }
