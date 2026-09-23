"""Public errors raised by the document preprocessing pipeline."""


class DocumentParseError(RuntimeError):
    """A source document could not be converted into the internal model."""


class DocumentCleaningError(RuntimeError):
    """Parsed elements could not be normalized safely."""


class DocumentClassificationError(RuntimeError):
    """A cleaned document could not be assigned a document type."""


class ChunkingError(RuntimeError):
    """A classified document could not be split into embedding chunks."""
