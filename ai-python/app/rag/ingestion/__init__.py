"""Structured preprocessing for hospital knowledge-base documents.

This package is not wired into the current upload route yet.  It has no vector
store or embedding side effects and importing it does not import Docling.
"""

from .adapter import LangChainDocumentAdapter, build_embedding_text
from .chunking import (
    ChunkingRouter,
    ChunkingStrategy,
    DirectoryChunkingStrategy,
    FAQChunkingStrategy,
    HospitalGuideChunkingStrategy,
    HuggingFaceTokenizer,
    HybridChunkingStrategy,
    MedicalPaperChunkingStrategy,
    PolicyChunkingStrategy,
    ProcedureChunkingStrategy,
    Tokenizer,
)
from .classifier import DocumentClassifier, RuleBasedDocumentClassifier
from .cleaner import DocumentCleaner
from .config import IngestionConfig
from .errors import (
    ChunkingError,
    DocumentClassificationError,
    DocumentCleaningError,
    DocumentParseError,
)
from .models import Chunk, DocumentType, ElementType, ParsedDocument, ParsedElement
from .parsers import (
    DoclingParser,
    DocumentParser,
    NativeDocumentParser,
    default_parser_for,
)
from .service import IngestionService

__all__ = [
    "Chunk",
    "ChunkingError",
    "ChunkingRouter",
    "ChunkingStrategy",
    "DirectoryChunkingStrategy",
    "DoclingParser",
    "DocumentClassificationError",
    "DocumentClassifier",
    "DocumentCleaner",
    "DocumentCleaningError",
    "DocumentParseError",
    "DocumentParser",
    "DocumentType",
    "ElementType",
    "FAQChunkingStrategy",
    "HospitalGuideChunkingStrategy",
    "HuggingFaceTokenizer",
    "HybridChunkingStrategy",
    "IngestionConfig",
    "IngestionService",
    "LangChainDocumentAdapter",
    "MedicalPaperChunkingStrategy",
    "NativeDocumentParser",
    "ParsedDocument",
    "ParsedElement",
    "PolicyChunkingStrategy",
    "ProcedureChunkingStrategy",
    "RuleBasedDocumentClassifier",
    "Tokenizer",
    "build_embedding_text",
    "default_parser_for",
]
