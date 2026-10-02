"""清理解析产生的多余空白和控制字符，保留原有医学内容与章节结构。"""

from __future__ import annotations

import re

from .models import ElementType, ParsedDocument, ParsedElement

_CONTROL_CHARACTERS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_INLINE_WHITESPACE = re.compile(r"[^\S\n]+")
_EXCESS_BLANK_LINES = re.compile(r"\n{3,}")
_FURNITURE = {ElementType.HEADER, ElementType.FOOTER}


class DocumentCleaner:
    """逐个清理元素，并把上级标题记录为每段内容的章节路径。"""

    def clean(self, document: ParsedDocument) -> ParsedDocument:
        cleaned: list[ParsedElement] = []
        headings: list[str] = []
        furniture: list[str] = []
        for element in document.elements:
            display = self._clean_text(element.text or "")
            search_source = element.search_text if element.search_text is not None else element.text
            search = self._clean_text(search_source or "")
            visible = display or search
            if element.element_type in _FURNITURE:
                if visible and visible not in furniture:
                    furniture.append(visible)
                continue
            is_asset_only = element.element_type in {
                ElementType.IMAGE,
                ElementType.PAGE_PLACEHOLDER,
            }
            if not visible and not is_asset_only:
                continue
            if element.element_type in {ElementType.TITLE, ElementType.HEADING}:
                level = max(1, element.heading_level or 1)
                headings = headings[: level - 1]
                headings.append(visible)
                section_path = tuple(headings)
            else:
                section_path = tuple(headings)
            cleaned.append(
                ParsedElement(
                    element_id=element.element_id,
                    element_type=element.element_type,
                    text=visible,
                    page_number=element.page_number,
                    heading_level=element.heading_level,
                    section_path=section_path,
                    metadata=dict(element.metadata),
                    raw_text=element.raw_text,
                    search_text=search or visible,
                    reading_order=element.reading_order,
                    provenance=element.provenance,
                    confidence=element.confidence,
                    structured_table=element.structured_table,
                    asset_refs=element.asset_refs,
                )
            )
        result = document.with_elements(cleaned)
        result.metadata = {**result.metadata, "page_furniture": furniture}
        return result

    @staticmethod
    def _clean_text(text: str) -> str:
        value = text.replace("\r\n", "\n").replace("\r", "\n")
        value = _CONTROL_CHARACTERS.sub("", value)
        value = _INLINE_WHITESPACE.sub(" ", value)
        value = "\n".join(line.strip() for line in value.splitlines())
        return _EXCESS_BLANK_LINES.sub("\n\n", value).strip()
