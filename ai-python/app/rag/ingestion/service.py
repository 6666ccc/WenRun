"""Orchestrates document preprocessing without writing to a vector store."""

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
from .parsers import DocumentParser, DocumentSource, default_parser_for

ParserResolver = Callable[[DocumentSource, str | None], DocumentParser]


def _file_name(source: DocumentSource, file_name: str | None) -> str:
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
    """Log a traceback whose exception and frames cannot expose document text."""

    # Loguru's diagnostic traceback can render frame locals.  Reusing a parser's
    # traceback could therefore expose source text even when our message is safe.
    # Start a new traceback at this boundary and retain the original error type as
    # a structured field instead.
    del cause
    safe_error = error_class(public_message)
    try:
        raise safe_error from None
    except error_class:
        logger.exception(log_message, *log_args)
        raise


class IngestionService:
    """Run the preprocessing pipeline and return embedding-ready documents."""

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
        try:
            strategy = ChunkingRouter(self.tokenizer, self.config).select_strategy(
                document_type
            )
            strategy_name = strategy.name
            chunks = strategy.split(cleaned)
            if not chunks:
                raise ValueError("chunking strategy returned no chunks")
            documents = self.adapter.to_documents(
                chunks,
                document=cleaned,
                document_type=document_type,
                chunk_strategy=strategy.name,
            )
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

        logger.info(
            "document_ingestion_completed document_id={} file_name={} parser={} document_type={} element_count={} chunk_strategy={} chunk_count={} duration_ms={}",
            document_id,
            safe_name,
            parsed.parser,
            document_type.value,
            len(cleaned.elements),
            strategy_name,
            len(documents),
            round((perf_counter() - started_at) * 1000),
        )
        return documents

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
