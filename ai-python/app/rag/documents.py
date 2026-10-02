"""院内 RAG 文档的展示格式化。只做纯转换，不检索、不调模型。"""

from langchain_core.documents import Document


def format_rag_context(documents: list[Document], start: int = 1) -> str:
    """把检索结果转成模型可读的院内资料上下文。start 用于多次检索时接续编号。"""

    blocks: list[str] = []
    for index, document in enumerate(documents, start=start):
        metadata = document.metadata or {}
        title = (
            metadata.get("source_name") or metadata.get("originalName") or "院内知识库"
        )
        page = metadata.get("page") or metadata.get("pageNumber") or "未标注"
        version = metadata.get("version") or "未标注"
        updated_at = metadata.get("updated_at") or "未标注"
        blocks.append(
            f"[S{index}] 来源：{title}；版本：{version}；页码：{page}；"
            f"更新时间：{updated_at}\n{document.page_content}"
        )
    return "\n\n".join(blocks)


def to_rag_sources(documents: list[Document], start: int = 1) -> list[dict]:
    """提取引用来源元数据，编号与 format_rag_context 保持一致。"""

    sources: list[dict] = []
    for index, document in enumerate(documents, start=start):
        metadata = document.metadata or {}
        raw_pages = metadata.get("page_numbers") or metadata.get("pages")
        if isinstance(raw_pages, (list, tuple, set)):
            pages = [page for page in raw_pages if page not in (None, "")]
        elif isinstance(raw_pages, str) and raw_pages.strip():
            pages = [value.strip() for value in raw_pages.split(",") if value.strip()]
        else:
            page = metadata.get("page") or metadata.get("pageNumber")
            pages = [page] if page not in (None, "") else []
        section_path = metadata.get("section_path") or metadata.get("sectionPath")
        if isinstance(section_path, str):
            section_path = [part.strip() for part in section_path.split(">") if part.strip()]
        elif not isinstance(section_path, (list, tuple)):
            section_path = []
        sources.append(
            {
                "id": f"S{index}",
                "document_id": metadata.get("document_id")
                or metadata.get("documentId"),
                "title": metadata.get("source_name") or metadata.get("originalName"),
                "version": metadata.get("version"),
                "build_id": metadata.get("build_id") or metadata.get("buildId"),
                "chunk_id": metadata.get("chunk_id") or metadata.get("chunkId"),
                "section": " > ".join(str(part) for part in section_path),
                "section_path": list(section_path),
                "pages": pages,
                "page": pages[0] if pages else None,
                "scope": metadata.get("scope", "public"),
                "source_asset_id": metadata.get("source_asset_id")
                or metadata.get("sourceAssetId"),
                "updated_at": metadata.get("updated_at") or metadata.get("updatedAt"),
            }
        )
    return sources
