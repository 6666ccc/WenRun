"""院内知识库检索工具。快速模式不再挂载；检索函数可供其他节点复用。"""

from langchain.tools import tool
from langchain_core.documents import Document
from loguru import logger

from app.rag.documents import format_rag_context
from app.rag.qdrant import get_hospital_retriever
from app.rag.safety import prepare_rag_documents


def retrieve_hospital_documents(query: str) -> list[Document]:
    """检索院内知识库。空 query 或后端故障时返回空列表，不把异常抛给模型。"""

    if not query.strip():
        return []
    try:
        documents = get_hospital_retriever().invoke(query)
        safe, _ = prepare_rag_documents(documents)
        return safe
    except Exception:  # noqa: BLE001 - retrieval is an optional fallback tool
        logger.exception("hospital_knowledge_retrieval_failed")
        return []


@tool
def search_hospital_knowledge(query: str) -> str:
    """检索温润诊所院内知识库，内容包括就诊须知、院内规定和院方发布的科普资料。

    query 必须是整理后的短检索词，不要传入患者原话全文。
    """

    documents = retrieve_hospital_documents(query)
    if not documents:
        return "（院内知识库无命中。）"
    return format_rag_context(documents)
