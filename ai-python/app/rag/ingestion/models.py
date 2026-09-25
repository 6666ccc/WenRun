"""文档预处理各阶段共用的数据形状，不绑定具体解析器或向量库。"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import Any


class ElementType(StrEnum):
    """解析后的内容类型，例如标题、段落或表格。"""

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
    """文档中的一个原始结构单元，保留页码和章节位置。"""

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
    """解析后的整份文档，由许多 ParsedElement 组成。"""

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
    """准备送去生成向量的一小段文字及其来源信息。"""

    text: str
    element_ids: tuple[str, ...]
    page_numbers: tuple[int, ...] = ()
    section_path: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
