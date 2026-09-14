from langchain_core.documents import Document

from app.rag.documents import format_rag_context, to_rag_sources

DOCS = [
    Document(page_content="多休息多喝水", metadata={"source_name": "院内资料", "page": 3}),
    Document(page_content="必要时就医", metadata={"document_id": "doc-9"}),
]


def test_format_rag_context_labels_each_block():
    text = format_rag_context(DOCS)

    assert "[S1] 来源：院内资料；版本：未标注；页码：3；更新时间：未标注" in text
    assert "多休息多喝水" in text
    assert "[S2] 来源：院内知识库；版本：未标注；页码：未标注" in text


def test_to_rag_sources_extracts_metadata():
    assert to_rag_sources(DOCS) == [
        {
            "id": "S1", "document_id": None, "title": "院内资料",
            "version": None, "page": 3, "chunk_id": None, "updated_at": None,
        },
        {
            "id": "S2", "document_id": "doc-9", "title": None,
            "version": None, "page": None, "chunk_id": None, "updated_at": None,
        },
    ]


def test_start_index_continues_numbering_across_calls():
    assert format_rag_context(DOCS, start=3).startswith("[S3]")
    assert [source["id"] for source in to_rag_sources(DOCS, start=3)] == ["S3", "S4"]
