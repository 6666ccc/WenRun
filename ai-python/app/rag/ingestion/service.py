"""文档入库前的预处理流水线，本文件本身不写向量库。

顺序是：按格式解析 → 清理提取瑕疵 → 判断文档类型 → 按结构切块 →
转成 LangChain Document。调用方 rag/ingest.py 再负责生成向量和发布版本。
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from time import perf_counter
from typing import Any, NoReturn

from langchain_core.documents import Document
from loguru import logger

from .adapter import LangChainDocumentAdapter
from .chunking import ChunkingRouter, HuggingFaceTokenizer, Tokenizer
from .classifier import DocumentClassifier, RuleBasedDocumentClassifier
from .cleaner import DocumentCleaner
from .config import IngestionConfig
from .errors import (
    ChunkingError,
    DocumentClassificationError,
    DocumentCleaningError,
    DocumentParseError,
)
from .models import PreparedIngestion
from .parsers import DocumentParser, DocumentSource, default_parser_for
from .quality import assess_quality

ParserResolver = Callable[[DocumentSource, str | None], DocumentParser]


def _file_name(source: DocumentSource, file_name: str | None) -> str:
    """从上传参数或路径提取供日志使用的文件名。"""
    if file_name:
        return Path(file_name).name
    if isinstance(source, (str, Path)):
        return Path(source).name
    return "unknown"


def _raise_logged(
    error_class: type[Exception],
    public_message: str,
    log_message: str,
    *log_args: object,
    cause: Exception,
) -> NoReturn:
    """统一报错并避免在日志堆栈里泄露上传文档的正文。"""

    # Loguru 的异常堆栈可能打印局部变量，直接沿用解析器异常会泄露文档正文。
    # 在这里重新抛出安全异常，只在结构化日志里保留原异常的类型。
    del cause
    safe_error = error_class(public_message)
    try:
        raise safe_error from None
    except error_class:
        logger.exception(log_message, *log_args)
        raise


class IngestionService:
    """运行所有预处理步骤，返回可用于生成向量的文档片段。"""

    def __init__(
        self,
        *,
        config: IngestionConfig | None = None,
        parser: DocumentParser | None = None,
        parser_resolver: ParserResolver = default_parser_for,
        cleaner: DocumentCleaner | None = None,
        classifier: DocumentClassifier | None = None,
        tokenizer: Tokenizer | None = None,
        adapter: LangChainDocumentAdapter | None = None,
    ) -> None:
        self.config = config or IngestionConfig()
        self.parser = parser
        self.parser_resolver = parser_resolver
        self.cleaner = cleaner or DocumentCleaner()
        self.classifier = classifier or RuleBasedDocumentClassifier()
        self.tokenizer = tokenizer or HuggingFaceTokenizer(self.config.tokenizer_model)
        self.adapter = adapter or LangChainDocumentAdapter()

    def ingest(
        self,
        source: DocumentSource,
        *,
        document_id: str,
        file_name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> list[Document]:
        """处理一个文件；没有可检索片段时仍按切块失败返回。"""
        prepared = self.prepare(
            source,
            document_id=document_id,
            file_name=file_name,
            metadata=metadata,
        )
        documents = prepared.to_documents()
        if not documents:
            _raise_logged(
                ChunkingError,
                f"failed to chunk {_file_name(source, file_name)}",
                "document_chunking_failed document_id={} file_name={} parser={} document_type={} chunk_strategy={} error_type={}",
                document_id,
                _file_name(source, file_name),
                prepared.parsed_document.parser,
                prepared.document_type.value,
                prepared.chunk_strategy,
                "EmptyChunkSet",
                cause=ValueError("chunking strategy returned no chunks"),
            )
        if not prepared.quality_report.can_publish:
            codes = [
                issue.code for issue in prepared.quality_report.issues if issue.blocking
            ]
            reason = ",".join(codes) or prepared.quality_report.status.value
            raise ValueError(f"资料未通过发布前质量检查：{reason}")
        return documents

    def prepare(
        self,
        source: DocumentSource,
        *,
        document_id: str,
        file_name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> PreparedIngestion:
        """解析并生成质量报告。没有检索片段时仍返回报告，供人工复核。"""
        started_at = perf_counter()
        safe_name = _file_name(source, file_name)
        selected_parser = self.parser
        try:
            selected_parser = selected_parser or self.parser_resolver(source, file_name)
            parsed = selected_parser.parse(
                source,
                document_id=document_id,
                file_name=file_name,
                metadata=metadata,
            )
            if not parsed.elements:
                raise ValueError("document parser returned no elements")
        except Exception as exc:  # noqa: BLE001 - normalize parser backends
            _raise_logged(
                DocumentParseError,
                f"failed to parse {safe_name}",
                "document_parse_failed document_id={} file_name={} parser={} error_type={}",
                document_id,
                safe_name,
                getattr(selected_parser, "name", "unresolved"),
                type(exc).__name__,
                cause=exc,
            )

        logger.info(
            "document_parsed document_id={} file_name={} parser={} element_count={}",
            document_id,
            safe_name,
            parsed.parser,
            len(parsed.elements),
        )
        try:
            cleaned = self.cleaner.clean(parsed)
        except Exception as exc:  # noqa: BLE001 - normalize cleaner implementations
            _raise_logged(
                DocumentCleaningError,
                f"failed to clean {safe_name}",
                "document_cleaning_failed document_id={} file_name={} parser={} error_type={}",
                document_id,
                safe_name,
                parsed.parser,
                type(exc).__name__,
                cause=exc,
            )

        try:
            document_type = self.classifier.classify(cleaned)
        except Exception as exc:  # noqa: BLE001 - normalize classifier implementations
            _raise_logged(
                DocumentClassificationError,
                f"failed to classify {safe_name}",
                "document_classification_failed document_id={} file_name={} parser={} error_type={}",
                document_id,
                safe_name,
                parsed.parser,
                type(exc).__name__,
                cause=exc,
            )

        strategy_name = "unresolved"
        chunks = []
        try:
            strategy = ChunkingRouter(self.tokenizer, self.config).select_strategy(
                document_type
            )
            strategy_name = strategy.name
            chunks = strategy.split(cleaned)
        except Exception as exc:  # noqa: BLE001 - normalize tokenizer/chunker backends
            _raise_logged(
                ChunkingError,
                f"failed to chunk {safe_name}",
                "document_chunking_failed document_id={} file_name={} parser={} document_type={} chunk_strategy={} error_type={}",
                document_id,
                safe_name,
                parsed.parser,
                document_type.value,
                strategy_name,
                type(exc).__name__,
                cause=exc,
            )

        quality = assess_quality(parsed, cleaned, len(chunks), chunks)
        logger.info(
            "document_ingestion_completed document_id={} file_name={} parser={} document_type={} element_count={} chunk_strategy={} chunk_count={} quality={} duration_ms={}",
            document_id,
            safe_name,
            parsed.parser,
            document_type.value,
            len(cleaned.elements),
            strategy_name,
            len(chunks),
            quality.status.value,
            round((perf_counter() - started_at) * 1000),
        )
        return PreparedIngestion(
            parsed_document=parsed,
            cleaned_document=cleaned,
            chunks=chunks,
            quality_report=quality,
            document_type=document_type,
            chunk_strategy=strategy_name,
        )

    def process(
        self,
        source: DocumentSource,
        *,
        document_id: str,
        file_name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> list[Document]:
        """Readable alias for callers that name the operation after the pipeline."""

        return self.ingest(
            source,
            document_id=document_id,
            file_name=file_name,
            metadata=metadata,
        )
