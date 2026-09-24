"""Conservative text cleanup that preserves document structure."""

from __future__ import annotations

import re
import unicodedata

from .models import ElementType, ParsedDocument, ParsedElement

_CONTROL_CHARACTERS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_INLINE_WHITESPACE = re.compile(r"[^\S\n]+")
_EXCESS_BLANK_LINES = re.compile(r"\n{3,}")


class DocumentCleaner:
    """Normalize extraction artifacts without rewriting medical content."""

    def clean(self, document: ParsedDocument) -> ParsedDocument:
        cleaned: list[ParsedElement] = []
        headings: list[str] = []
        for element in document.elements:
            text = self._clean_text(element.text)
            if not text:
                continue
            if element.element_type in {ElementType.TITLE, ElementType.HEADING}:
                level = max(1, element.heading_level or 1)
                headings = headings[: level - 1]
                headings.append(text)
                section_path = tuple(headings)
            else:
                section_path = tuple(headings)
            cleaned.append(
                ParsedElement(
                    element_id=element.element_id,
                    element_type=element.element_type,
                    text=text,
                    page_number=element.page_number,
                    heading_level=element.heading_level,
                    section_path=section_path,
                    metadata=dict(element.metadata),
                )
            )
        if not cleaned:
            raise ValueError("document contains no usable text after cleaning")
        return document.with_elements(cleaned)

    @staticmethod
    def _clean_text(text: str) -> str:
        value = unicodedata.normalize("NFKC", text)
        value = value.replace("\r\n", "\n").replace("\r", "\n")
        value = _CONTROL_CHARACTERS.sub("", value)
        value = _INLINE_WHITESPACE.sub(" ", value)
        value = "\n".join(line.strip() for line in value.splitlines())
        return _EXCESS_BLANK_LINES.sub("\n\n", value).strip()
