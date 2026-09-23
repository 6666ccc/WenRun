"""Internal, provider-independent models used during ingestion."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import Any


class ElementType(StrEnum):
    TITLE = "title"
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST_ITEM = "list_item"
    TABLE = "table"
    CAPTION = "caption"


class DocumentType(StrEnum):
    """Hospital document families with meaningfully different layouts."""

    FAQ = "faq"
    PROCEDURE = "procedure"
    POLICY = "policy"
    DIRECTORY = "directory"
    HOSPITAL_GUIDE = "hospital_guide"
    MEDICAL_PAPER = "medical_paper"
    GENERAL = "general"


@dataclass(slots=True)
class ParsedElement:
    element_id: str
    element_type: ElementType
    text: str
    page_number: int | None = None
    heading_level: int | None = None
    section_path: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def with_text(self, text: str) -> ParsedElement:
        return replace(self, text=text, metadata=dict(self.metadata))


@dataclass(slots=True)
class ParsedDocument:
    document_id: str
    file_name: str
    elements: list[ParsedElement]
    parser: str
    source_type: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def with_elements(self, elements: list[ParsedElement]) -> ParsedDocument:
        return replace(self, elements=elements, metadata=dict(self.metadata))


@dataclass(slots=True)
class Chunk:
    text: str
    element_ids: tuple[str, ...]
    page_numbers: tuple[int, ...] = ()
    section_path: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
