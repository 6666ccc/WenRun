##该节点：先检索院内 RAG；未命中时，再由 Agent 整理检索词并决定是否联网。
from app.graphs.hospital.memory import recent_messages
from app.graphs.hospital.state import State
from app.graphs.hospital.tools.search import web_search
from app.models.chat import model
from app.rag.qdrant import get_hospital_retriever
from langchain.agents import create_agent
from langchain_core.documents import Document
from langchain_core.messages import SystemMessage
from loguru import logger

KNOWLEDGE_SYSTEM_PROMPT = """你是温润诊所的患者端知识助手。用简短、尊重、有温度的中文直接回复患者。

工作流程（必须按顺序，不要跳步）：
1. 系统已经优先检索过院内知识库。进入本 Agent 代表院内资料未命中，不要假装查过或引用院内资料。
2. 未命中后，先把患者原话整理成一句短检索词：去掉寒暄、情绪、重复和无关细节，只保留真正要查的问题。
   例：原话「你好，我最近心情很难受……所以感冒吃什么药」→ 检索词「感冒吃什么药」。
3. 调用 web_search，query 只能是整理后的短检索词，禁止把整段原话丢给搜索。
4. 只根据工具返回的片段做摘要。不要用自己的医学知识补全。

把关：
- 只回答医疗知识。需要事实依据（用药、护理、症状说明、检查前后医学注意等）时必须先 web_search，再回答。
- 本院楼层、营业时间、就诊须知、科室目录、号源、排班、挂号：不要搜网页，一句交给业务助手或到院咨询。
- 检索为空或与问题无关：说明公开资料没有足够依据，请换个问法或到院评估。

出处规则：
- 正文（含分点）禁止出现 [1]、[2]、[S1] 等方括号引用标记，不要把检索编号抄进回复。
- 文末用「参考来源」列出标题和完整链接，链接必须来自检索结果，禁止编造 URL。序号写成「1. 标题」，不要写成 [1]。
- 没有链接的句子不要写成确定事实。

你只处理这些内容：
- 症状、疾病、用药、护理、是否需要就医
- 检查前后的医学注意（如是否空腹抽血）
- 某科通常看什么病（分科医疗知识，不是本院楼层或号源）

你不要做：
- 不回答本院楼层、营业时间、就诊须知、科室列表、排班
- 不编造检索结果里没有的药名、剂量、疗效
- 不下诊断、不说「你就是某病」、不承诺疗效、不开处方
- 不挂号、不查号源、不查医生排班、不编造医院实时数据
- 不闲聊、不陪聊；寒暄最多一句带过，立刻回到医疗知识摘要
- 不说「我已经帮你挂好号」——那些由其他节点处理

多意图时：患者一句话里若同时有医疗提问和寒暄/挂号/院务，你只回答医疗知识部分。其余留给其他助手。

急症或明确危险（如胸痛、大出血、呼吸困难、想伤害自己）：先明确建议立即拨打急救或前往急诊，再视检索结果做极短补充；没有资料就不要展开。

回复结构（检索有内容时）：
1. 一两句直接回答问题
2. 必要注意点（有则写，无则省略）
3. 参考来源（标题、链接；不要用 [1] 这类方括号编号）
4. 一句免责：以上根据公开网页整理，不能代替面诊，也不代表本院规定

示例：
- 「你好，我最近心情很难受……所以感冒吃什么药」→ 整理为「感冒吃什么药」再 web_search，然后摘要并列出链接。
- 「儿科在几楼」「诊所几点开门」→ 不要联网，只说院务请到前台或电话确认。
- 检索为空 → 说明暂无依据，建议到院评估；不自行判断严重程度。
- 「帮我挂明天内科」→ 不要联网，只说挂号由业务助手处理。
"""

agent = create_agent(
    model=model,
    tools=[web_search],
    system_prompt=KNOWLEDGE_SYSTEM_PROMPT,
)


# 步骤一：从 LangGraph State 中取得最后一条用户消息，作为向量检索 query。
def _last_user_query(state: State) -> str:
    for message in reversed(state.get("messages") or []):
        if getattr(message, "type", None) in {"human", "user"}:
            content = getattr(message, "content", "")
            if isinstance(content, str):
                return content.strip()
    return ""


# 步骤二：把 Retriever 返回的 Document 转为模型可阅读的院内资料上下文。
def _format_rag_context(documents: list[Document]) -> str:
    blocks: list[str] = []
    for index, document in enumerate(documents, start=1):
        metadata = document.metadata or {}
        title = (
            metadata.get("source_name") or metadata.get("originalName") or "院内知识库"
        )
        page = metadata.get("page") or metadata.get("pageNumber") or "未标注"
        blocks.append(
            f"[S{index}] 来源：{title}；页码：{page}\n{document.page_content}"
        )
    return "\n\n".join(blocks)


# 步骤三：把命中资料的元数据保存到 State，最终响应可以展示引用来源。
def _to_rag_sources(documents: list[Document]) -> list[dict]:
    sources: list[dict] = []
    for index, document in enumerate(documents, start=1):
        metadata = document.metadata or {}
        sources.append(
            {
                "id": f"S{index}",
                "document_id": metadata.get("document_id")
                or metadata.get("documentId"),
                "title": metadata.get("source_name") or metadata.get("originalName"),
                "page": metadata.get("page") or metadata.get("pageNumber"),
            }
        )
    return sources


# 步骤四：院内资料未命中时，保留原有 web_search Agent 作为兜底。
def _web_fallback_reply(state: State) -> str:
    result = agent.invoke({"messages": recent_messages(state)})
    messages = result.get("messages") or []
    last = messages[-1] if messages else None
    content = getattr(last, "content", "") if last is not None else ""
    return content if isinstance(content, str) else str(content)


def knowledge_node(state: State) -> dict:
    # 步骤五：只有意图路由选中 knowledge 时，才查询院内知识库。
    selected = state.get("selected_agents") or []
    if "knowledge" not in selected:
        return {}

    # 步骤六：将用户原问题传给 Retriever；内部会执行 embedding 与 Qdrant 相似度检索。
    query = _last_user_query(state)
    if not query:
        return {"knowledge_reply": "请告诉我您想咨询的具体问题。", "rag_sources": []}

    try:
        documents = get_hospital_retriever().invoke(query)
    except Exception:
        logger.exception("RAG retrieval failed")
        return {
            "knowledge_reply": "院内知识库暂时不可用，请稍后再试或咨询医院工作人员。",
            "rag_sources": [],
        }

    # 步骤七：未命中足够相关的院内资料时，交给原有联网 Agent 兜底。
    if not documents:
        return {
            "knowledge_reply": _web_fallback_reply(state),
            "rag_sources": [],
        }

    # 步骤八：命中后将资料作为 SystemMessage 上下文，让模型只能依据院内资料回答。
    # 此分支直接调用不带工具的基础 model，不能调用带 web_search 的 agent：
    # 1. 从代码层面保证 RAG 已命中时不会再次触发网页搜索；
    # 2. model.invoke 接收消息列表并直接返回 AIMessage，便于正确读取回答正文。
    context = _format_rag_context(documents)
    rag_messages = [
        SystemMessage(
            content=(
                "你是医院知识助手。只能依据【院内资料】回答用户问题。"
                "资料未说明的内容必须明确说‘院内资料未说明’，不得猜测或补充。"
                "不要在回复中输出 [S1]、[1] 等方括号编号。\n\n"
                f"【院内资料】\n{context}"
            )
        ),
        *recent_messages(state),
    ]
    answer = model.invoke(rag_messages)

    # 步骤九：model.invoke 返回 AIMessage；取出正文，并同时保存 RAG 来源元数据。
    content = getattr(answer, "content", "")
    return {
        "knowledge_reply": content if isinstance(content, str) else str(content),
        "rag_sources": _to_rag_sources(documents),
    }
