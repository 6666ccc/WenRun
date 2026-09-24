import re
import subprocess
import sys

import pytest
from loguru import logger

from app.rag.ingestion import (
    ChunkingError,
    DocumentCleaner,
    DocumentParseError,
    DocumentType,
    ElementType,
    IngestionConfig,
    IngestionService,
    NativeDocumentParser,
    ParsedDocument,
    ParsedElement,
    RuleBasedDocumentClassifier,
)
from app.rag.ingestion.chunking import ChunkingRouter
from app.rag.ingestion.parsers import DocumentParser


class FakeTokenizer:
    """One Han character is one token; adjacent ASCII letters/digits are one."""

    _parts = re.compile(r"[A-Za-z0-9]+|[\u3400-\u9fff]|[^\s]")

    def encode(self, text, **kwargs):
        return self._parts.findall(text)

    def decode(self, tokens, **kwargs):
        return "".join(tokens)


def _document(*elements: ParsedElement) -> ParsedDocument:
    return ParsedDocument(
        document_id="doc-1",
        file_name="guide.md",
        parser="fake",
        source_type="md",
        elements=list(elements),
    )


def test_markdown_parser_and_cleaner_preserve_structure():
    parsed = NativeDocumentParser().parse(
        "# 门诊须知\n\n## 办理流程\n\n- 挂号\n- 候诊".encode(),
        document_id="doc-1",
        file_name="guide.md",
    )
    cleaned = DocumentCleaner().clean(parsed)

    assert [element.element_type for element in cleaned.elements] == [
        ElementType.TITLE,
        ElementType.HEADING,
        ElementType.LIST_ITEM,
        ElementType.LIST_ITEM,
    ]
    assert cleaned.elements[-1].section_path == ("门诊须知", "办理流程")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("常见问题\n问：如何预约？\n答：使用小程序。", DocumentType.FAQ),
        ("就诊流程\n第一步：挂号\n第二步：候诊", DocumentType.PROCEDURE),
        ("病历管理制度\n第一条 适用范围", DocumentType.POLICY),
        ("科室目录\n联系电话：123", DocumentType.DIRECTORY),
        ("门诊服务\n挂号流程\n退号规则", DocumentType.HOSPITAL_GUIDE),
        ("医院停车场开放时间说明", DocumentType.GENERAL),
    ],
)
def test_rule_classifier_covers_document_families(text, expected):
    document = _document(
        ParsedElement("e1", ElementType.PARAGRAPH, text),
    )

    assert RuleBasedDocumentClassifier().classify(document) == expected


def test_hybrid_prefers_sentence_boundaries_before_token_limit():
    config = IngestionConfig(max_tokens=10, overlap_tokens=0, min_chunk_tokens=2)
    document = _document(
        ParsedElement(
            "e1",
            ElementType.PARAGRAPH,
            "挂号完成。请按预约时间候诊。检查结束。",
        ),
    )
    strategy = ChunkingRouter(FakeTokenizer(), config).select_strategy(
        DocumentType.GENERAL
    )

    chunks = strategy.split(document)

    assert strategy.name == "hybrid"
    assert [chunk.text for chunk in chunks] == [
        "挂号完成。",
        "请按预约时间候诊。",
        "检查结束。",
    ]
    assert all(len(FakeTokenizer().encode(chunk.text)) <= 10 for chunk in chunks)


def test_single_oversized_sentence_uses_token_window_as_fallback():
    config = IngestionConfig(max_tokens=8, overlap_tokens=2, min_chunk_tokens=2)
    document = _document(
        ParsedElement("e1", ElementType.PARAGRAPH, "一二三四五六七八九十。"),
    )
    strategy = ChunkingRouter(FakeTokenizer(), config).select_strategy(
        DocumentType.GENERAL
    )

    chunks = strategy.split(document)

    assert len(chunks) == 2
    assert all(len(FakeTokenizer().encode(chunk.text)) <= 8 for chunk in chunks)


def test_hospital_guide_keeps_short_sections_in_separate_chunks():
    service = IngestionService(
        parser=NativeDocumentParser(), tokenizer=FakeTokenizer()
    )

    documents = service.ingest(
        (
            "# 门诊服务\n\n"
            "## 挂号流程\n\n请携带身份证在自助机挂号。\n\n"
            "## 退号规则\n\n就诊前可以原路退号。"
        ).encode(),
        document_id="guide-1",
        file_name="门诊指南.md",
    )

    assert len(documents) == 2
    assert {document.metadata["document_type"] for document in documents} == {
        "hospital_guide"
    }
    assert {document.metadata["chunk_strategy"] for document in documents} == {
        "guide_sections"
    }
    assert [document.metadata["section_path"] for document in documents] == [
        "门诊服务 > 挂号流程",
        "门诊服务 > 退号规则",
    ]
    assert "退号规则" not in documents[0].page_content
    assert "挂号流程" not in documents[1].page_content


def test_faq_emits_exactly_one_chunk_per_question_answer_pair():
    service = IngestionService(
        parser=NativeDocumentParser(), tokenizer=FakeTokenizer()
    )

    documents = service.ingest(
        (
            "# 常见问题\n\n"
            "问：如何预约？\n\n答：使用医院小程序。\n\n"
            "问：如何取消？\n\n答：在预约记录中取消。"
        ).encode(),
        document_id="faq-2",
        file_name="门诊FAQ.md",
    )

    assert len(documents) == 2
    assert all(document.metadata["document_type"] == "faq" for document in documents)
    assert all(
        document.metadata["chunk_strategy"] == "faq_pair"
        for document in documents
    )
    assert "如何取消" not in documents[0].page_content
    assert "如何预约" not in documents[1].page_content


def test_medical_paper_headings_select_paper_section_strategy():
    service = IngestionService(
        parser=NativeDocumentParser(), tokenizer=FakeTokenizer()
    )

    documents = service.ingest(
        (
            "# 高血压随访研究\n\n"
            "## 摘要\n\n研究摘要。\n\n"
            "## 讨论\n\n研究讨论。\n\n"
            "## 结论\n\n研究结论。"
        ).encode(),
        document_id="paper-1",
        file_name="随访研究.md",
    )

    assert len(documents) == 3
    assert all(
        document.metadata["document_type"] == "medical_paper"
        for document in documents
    )
    assert [document.metadata["section_path"] for document in documents] == [
        "高血压随访研究 > 摘要",
        "高血压随访研究 > 讨论",
        "高血压随访研究 > 结论",
    ]


def test_service_returns_enriched_langchain_documents_without_external_calls():
    service = IngestionService(
        parser=NativeDocumentParser(),
        tokenizer=FakeTokenizer(),
        config=IngestionConfig(max_tokens=20, overlap_tokens=2),
    )

    documents = service.ingest(
        "# 常见问题\n\n问：如何预约？\n\n答：使用医院小程序。".encode(),
        document_id="faq-1",
        file_name="预约FAQ.md",
        metadata={"version": 3},
    )

    assert documents
    assert documents[0].page_content.startswith("文档：预约FAQ")
    assert documents[0].metadata["document_id"] == "faq-1"
    assert documents[0].metadata["document_type"] == "faq"
    assert documents[0].metadata["chunk_strategy"] == "faq_pair"
    assert documents[0].metadata["version"] == 3


class BrokenParser(DocumentParser):
    name = "broken"

    def parse(self, source, *, document_id, file_name=None, metadata=None):
        detail = "secret body must not be surfaced"
        raise OSError(detail)


def test_service_wraps_parser_failures_in_public_error():
    service = IngestionService(parser=BrokenParser(), tokenizer=FakeTokenizer())
    records = []
    sink_id = logger.add(records.append, format="{message}\n{exception}")
    try:
        with pytest.raises(DocumentParseError) as captured:
            service.ingest(
                b"private content", document_id="bad-1", file_name="bad.txt"
            )
    finally:
        logger.remove(sink_id)

    assert "secret body" not in str(captured.value)
    assert "secret body" not in "".join(records)
    assert "private content" not in "".join(records)


class BrokenTokenizer(FakeTokenizer):
    def encode(self, text, **kwargs):
        raise RuntimeError("tokenizer failed")


def test_service_wraps_chunking_failures():
    service = IngestionService(
        parser=NativeDocumentParser(), tokenizer=BrokenTokenizer()
    )

    with pytest.raises(ChunkingError):
        service.ingest(b"usable text", document_id="bad-2", file_name="bad.txt")


def test_importing_ingestion_does_not_import_docling_or_torch():
    script = (
        "import sys; "
        "import app.main; import app.rag.ingestion; import app.rag.ingest; "
        "import app.rag.chroma; "
        "assert not any(k == 'docling' or k.startswith('docling.') for k in sys.modules); "
        "assert not any(k == 'torch' or k.startswith('torch.') for k in sys.modules)"
    )

    subprocess.run([sys.executable, "-c", script], check=True)
