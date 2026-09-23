"""Convert internal chunks into the LangChain boundary type."""

from __future__ import annotations

from pathlib import Path

from langchain_core.documents import Document

from .models import Chunk, DocumentType, ParsedDocument


def build_embedding_text(chunk: Chunk, document: ParsedDocument) -> str:
    """Add compact structural context to content before embedding."""

    context = [f"文档：{Path(document.file_name).stem}"]
    if chunk.section_path:
        context.append(f"章节：{' > '.join(chunk.section_path)}")
    context.append(chunk.text)
    return "\n".join(context)


class LangChainDocumentAdapter:
    def to_documents(
        self,
        chunks: list[Chunk],
        *,
        document: ParsedDocument,
        document_type: DocumentType,
        chunk_strategy: str,
    ) -> list[Document]:
        total = len(chunks)
        result: list[Document] = []
        for index, chunk in enumerate(chunks):
            metadata = {
                **document.metadata,
                **chunk.metadata,
                "document_id": document.document_id,
                "source_name": document.file_name,
                "file_type": document.metadata.get("file_type", document.source_type),
                "parser": document.parser,
                "document_type": document_type.value,
                "chunk_strategy": chunk_strategy,
                "chunk_index": index,
                "chunk_count": total,
                "element_ids": ",".join(chunk.element_ids),
                "section_path": " > ".join(chunk.section_path),
                "page_numbers": ",".join(str(page) for page in chunk.page_numbers),
            }
            if chunk.page_numbers:
                metadata["page"] = chunk.page_numbers[0]
            result.append(
                Document(
                    page_content=build_embedding_text(chunk, document),
                    metadata=metadata,
                )
            )
        return result
