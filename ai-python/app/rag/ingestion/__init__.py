"""院内资料上传时使用的结构化预处理包。

上传入口 rag/ingest.py 会调用 IngestionService，完成解析、清理、分类和切块。
本包只返回待生成向量的文档片段，不直接写向量库；导入时也不会加载 Docling。
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
