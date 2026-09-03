"""快速模式：单个全能 Agent 直接作答，跳过意图路由与汇总。

工具循环写在本节点内部而不是用嵌套 create_agent：只有根图节点产生的模型分片
才会被 SSE 路由转发，嵌套子图的分片会被命名空间过滤掉，那样快速模式就没有流式了。
"""

from langchain_core.messages import AIMessage, AIMessageChunk, SystemMessage, ToolMessage
from loguru import logger

from app.graphs.hospital.memory import recent_messages, reset_turn_fields
from app.graphs.hospital.state import State
from app.graphs.hospital.tools.knowledge_base import (
    retrieve_hospital_documents,
    search_hospital_knowledge,
)
from app.graphs.hospital.tools.search import web_search
from app.models.chat import model
from app.rag.documents import format_rag_context, to_rag_sources

FAST_TOOLS = [search_hospital_knowledge, web_search]
MAX_TOOL_ITERATIONS = 3
EMPTY_REPLY_FALLBACK = "抱歉，我这次没能给出有效回答，请换个说法再问一次。"

FAST_SYSTEM_PROMPT = """你是温润诊所患者端的快速助手。患者主动开启了「快速模式」，希望更快拿到回答。
用简短、尊重、有温度的中文直接回复。不要提及内部流程或工具名。除了引导患者关闭快速模式以外，不要提及「快速模式」这个词。

你一个人同时承担闲聊陪伴和医疗知识：
- 问候、自我介绍、闲聊、感谢、告别、情绪倾诉、与就诊无关的日常话题：简短接住，不评判、不说教；需要时轻轻引回看病或挂号。
- 症状、疾病、用药、护理、是否需要就医、检查前后注意事项、某科通常看什么病：按下面的检索规则作答。
- 一句话里同时有寒暄和医疗提问：两件事都回，寒暄一两句即可，重点放在医疗部分。
- 一句话里同时有医疗/寒暄和号源排班：先答能答的部分，号源那句按下面的业务规则推回，不要编造。

检索规则（需要事实依据时必须先查再答，不要凭记忆回答用药和剂量）：
1. 先调用 search_hospital_knowledge，查院内知识库。
2. 院内无命中时，再调用 web_search，query 只能是整理后的短检索词，不要把患者原话整段丢进去。
3. 只根据检索片段作答，不要用自己的医学知识补全。两个工具都没有依据时，如实说明公开资料不足，请患者到院评估。
4. 纯寒暄、情绪陪伴、明显不需要事实依据的问题，不要调用任何工具，直接回答。
5. 决定调用工具的那一轮不要输出任何对患者说的话，等工具结果回来再作答。

院务与实时业务（这两类都不是网页能回答的）：
- 本院楼层、营业时间、就诊须知：可以先查院内知识库；没查到就请到前台或电话确认，不要为此联网，不要编造。
- 你没有医院实时业务数据，也没有查询这些数据的工具。患者问号源、排班、某位医生某天有没有号、本院有哪些科室、某科有哪些医生、我的预约时：一句话说明快速模式查不了这些实时信息，请关闭快速模式再问一次。绝对不要编造科室名、医生、日期、余号、费用。
- 挂号、退号、缴费：即使关闭快速模式也不能代办，请患者到挂号或缴费页面自行办理。不要说「我已经帮你挂好号 / 查过排班」。

出处规则：
- 正文（含分点）禁止出现 [1]、[2]、[S1] 等方括号编号。
- 用到 web_search 结果时，文末用「参考来源」列出标题和完整链接，序号写成「1. 标题」，不要写成 [1]。链接必须来自检索结果，禁止编造 URL。没有链接的句子不要写成确定事实。文末加一句：以上根据公开网页整理，不能代替面诊，也不代表本院规定。
- 用到院内资料时，正文里自然说明「根据院内资料」即可，不要抄编号。

急症或明确危险（如胸痛、大出血、呼吸困难、想伤害自己）：立刻明确建议拨打急救或前往急诊，再视检索结果做极短补充，没有依据就不要展开。

示例：
- 「你好」→ 简短问好，询问可以帮什么。
- 「感冒吃什么药」→ 先查院内库，未命中再联网，按片段作答并列出参考来源。
- 「儿科在几楼」→ 可查院内库；没查到就请到前台确认，不编造楼层，不联网。
- 「明天下午张医生还有号吗」→ 说明快速模式查不了实时号源，请关闭快速模式再问，或到挂号页面查看。
- 「帮我挂明天内科」→ 说明不能代为挂号，请到挂号页面办理。
- 「谢谢你啊，顺便问问感冒吃什么药」→ 先致谢一两句，再按检索规则回答用药。
"""


def _stream_turn(bound_model, messages) -> tuple[AIMessageChunk | None, str]:
    """跑一轮模型。返回聚合后的分片（用于读 tool_calls）与纯文本。

    用 stream 而非 invoke，分片才能被 LangGraph 的 messages 流立即转发给 SSE 路由。
    """

    aggregated: AIMessageChunk | None = None
    parts: list[str] = []
    for chunk in bound_model.stream(messages):
        aggregated = chunk if aggregated is None else aggregated + chunk
        content = getattr(chunk, "content", "")
        if isinstance(content, str) and content:
            parts.append(content)
    return aggregated, "".join(parts)


def _run_tool_call(call: dict, collected: list[dict]) -> str:
    """执行一次工具调用。院内检索走底层函数，以便同时收集引用来源。"""

    name = call.get("name")
    args = call.get("args") or {}

    if name == search_hospital_knowledge.name:
        documents = retrieve_hospital_documents(str(args.get("query") or ""))
        if not documents:
            return "（院内知识库无命中，可改用 web_search 查询公开资料。）"
        start = len(collected) + 1
        collected.extend(to_rag_sources(documents, start=start))
        return format_rag_context(documents, start=start)

    if name == web_search.name:
        return web_search.invoke(args)

    logger.warning("fast_node_unknown_tool name={}", name)
    return f"（没有名为 {name} 的工具，请直接回答或改用其他工具。）"


def fast_node(state: State) -> dict:
    bound_model = model.bind_tools(FAST_TOOLS)
    messages = [SystemMessage(content=FAST_SYSTEM_PROMPT), *recent_messages(state)]
    collected: list[dict] = []
    text = ""

    for _ in range(MAX_TOOL_ITERATIONS):
        reply, text = _stream_turn(bound_model, messages)
        tool_calls = getattr(reply, "tool_calls", None) if reply is not None else None
        if not tool_calls:
            break
        messages.append(reply)
        for call in tool_calls:
            messages.append(
                ToolMessage(
                    content=_run_tool_call(call, collected),
                    tool_call_id=call.get("id") or "",
                )
            )
    else:
        # 工具预算耗尽仍在调工具：去掉工具再问一次，逼出一个面向患者的答案。
        logger.warning(
            "fast_node_tool_budget_exhausted conversation_id={}",
            state.get("conversation_id"),
        )
        _, text = _stream_turn(model, messages)

    final_reply = text.strip() or EMPTY_REPLY_FALLBACK
    # 工具循环里的中间消息不写回 State：checkpoint 结构必须与正常模式保持一致。
    # 显式清空 selected_agents：快速图没有 begin_node，否则会串出上一轮正常模式的路由。
    return {
        **reset_turn_fields(),
        "selected_agents": [],
        "final_reply": final_reply,
        "rag_sources": collected,
        "messages": [AIMessage(content=final_reply)],
    }
