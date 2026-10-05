"""Typed, serializable structures shared by parsers, quality checks and chunking.

``ParsedElement.text`` remains as the compatibility view used by existing callers.
New code should use ``raw_text`` for the parser output and ``search_text`` for the
normalized retrieval representation.  Source locations are deliberately optional:
many formats (notably DOCX before rendering) do not have a trustworthy page map.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass
from enum import StrEnum
from typing import Any


class ElementType(StrEnum):
    """Semantic content types emitted by parsers."""

    TITLE = "title"
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST_ITEM = "list_item"
    TABLE = "table"
    CAPTION = "caption"
    IMAGE = "image"
    FORMULA = "formula"
    HEADER = "header"
    FOOTER = "footer"
    PAGE_PLACEHOLDER = "page_placeholder"


class DocumentType(StrEnum):
    """Hospital document families with meaningfully different layouts."""

    FAQ = "faq"
    PROCEDURE = "procedure"
    POLICY = "policy"
    DIRECTORY = "directory"
    HOSPITAL_GUIDE = "hospital_guide"
    MEDICAL_PAPER = "medical_paper"
    GENERAL = "general"


class CoordinateOrigin(StrEnum):
    TOP_LEFT = "top_left"
    BOTTOM_LEFT = "bottom_left"
    UNKNOWN = "unknown"


class QualityStatus(StrEnum):
    PASS = "pass"
    REVIEW = "review"
    BLOCKED = "blocked"


@dataclass(slots=True, frozen=True)
class SourceProvenance:
    """A source page or region. Page numbers use the source's one-based numbering."""

    page_number: int | None = None
    bbox: tuple[float, float, float, float] | None = None
    page_width: float | None = None
    page_height: float | None = None
    coordinate_origin: CoordinateOrigin = CoordinateOrigin.UNKNOWN
    source_region: str | None = None


@dataclass(slots=True, frozen=True)
class AssetReference:
    """A pointer into an archived source or a separately stored extracted asset."""

    asset_id: str
    media_type: str | None = None
    source_kind: str = "source_file"
    source_locator: str | None = None
    requires_extraction: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class TableCell:
    row: int
    column: int
    text: str
    row_span: int = 1
    column_span: int = 1
    is_header: bool = False
    continuation: bool = False


@dataclass(slots=True)
class StructuredTable:
    """Logical table cells plus the context needed to interpret their values."""

    rows: list[list[str]] = field(default_factory=list)
    cells: list[TableCell] = field(default_factory=list)
    header_rows: int = 0
    units: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    caption: str | None = None
    structure_source: str = "unknown"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ParsedElement:
    """A typed block and every known source location that supports it."""

    element_id: str
    element_type: ElementType
    text: str = ""
    # Legacy page_number and text fields stay in their original positions.
    page_number: int | None = None
    heading_level: int | None = None
    section_path: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    raw_text: str | None = None
    search_text: str | None = None
    reading_order: int | None = None
    provenance: tuple[SourceProvenance, ...] = ()
    confidence: float | None = None
    structured_table: StructuredTable | None = None
    asset_refs: tuple[AssetReference, ...] = ()

    def __post_init__(self) -> None:
        if self.raw_text is None:
            self.raw_text = self.text
        if self.search_text is None:
            self.search_text = self.text
        if self.provenance and self.page_number is None:
            self.page_number = next(
                (item.page_number for item in self.provenance if item.page_number),
                None,
            )
        elif self.page_number is not None and not self.provenance:
            self.provenance = (SourceProvenance(page_number=self.page_number),)
        if self.page_number is None and self.provenance:
            self.page_number = next(
                (item.page_number for item in self.provenance if item.page_number),
                None,
            )


@dataclass(slots=True)
class ParsedDocument:
    """Parser output with an auditable parser identity and configuration."""

    document_id: str
    file_name: str
    elements: list[ParsedElement]
    parser: str
    source_type: str
    metadata: dict[str, Any] = field(default_factory=dict)
    parser_version: str = "unknown"
    parser_config: dict[str, Any] = field(default_factory=dict)

    def with_elements(self, elements: list[ParsedElement]) -> ParsedDocument:
        return ParsedDocument(
            document_id=self.document_id,
            file_name=self.file_name,
            elements=elements,
            parser=self.parser,
            source_type=self.source_type,
            metadata=dict(self.metadata),
            parser_version=self.parser_version,
            parser_config=dict(self.parser_config),
        )


@dataclass(slots=True, frozen=True)
class QualityIssue:
    code: str
    severity: str
    blocking: bool
    message: str
    element_id: str | None = None
    page_number: int | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class QualityReport:
    status: QualityStatus
    issues: list[QualityIssue] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    generated_by: str = "deterministic_rules_v1"

    @property
    def can_publish(self) -> bool:
        return self.status == QualityStatus.PASS and not any(
            issue.blocking for issue in self.issues
        )


@dataclass(slots=True)
class Chunk:
    """Retrieval text, linked element ids, all known pages and evidence metadata."""

    text: str
    element_ids: tuple[str, ...]
    page_numbers: tuple[int, ...] = ()
    section_path: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    source_locations: tuple[SourceProvenance, ...] = ()
    asset_refs: tuple[AssetReference, ...] = ()


@dataclass(slots=True)
class PreparedIngestion:
    """Serializable parse/retrieval artifact ready for review and index building."""

    parsed_document: ParsedDocument
    cleaned_document: ParsedDocument
    chunks: list[Chunk]
    quality_report: QualityReport
    document_type: DocumentType
    chunk_strategy: str

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe artifact; asset bytes must be stored separately."""

        parsed = self.parsed_document
        return {
            "schema_version": 1,
            "document_id": parsed.document_id,
            "file_name": parsed.file_name,
            "parser": parsed.parser,
            "parser_version": parsed.parser_version,
            "parser_config": to_primitive(parsed.parser_config),
            "source_type": parsed.source_type,
            "source_sha256": parsed.metadata.get("source_sha256"),
            "parsed_document": parsed_document_to_dict(parsed),
            "cleaned_document": parsed_document_to_dict(self.cleaned_document),
            "chunks": to_primitive(self.chunks),
            "document_type": self.document_type.value,
            "chunk_strategy": self.chunk_strategy,
            "quality_report": to_primitive(self.quality_report),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> PreparedIngestion:
        """Restore stored artifacts; unknown keys are ignored for forward compatibility."""

        raw_doc = payload.get("parsed_document") or {}
        clean_doc = payload.get("cleaned_document") or raw_doc
        parsed = parsed_document_from_dict(raw_doc)
        cleaned = parsed_document_from_dict(clean_doc)
        chunks = [chunk_from_dict(item) for item in payload.get("chunks", [])]
        quality_raw = payload.get("quality_report") or {}
        issues = [
            QualityIssue(
                code=str(item.get("code", "unknown")),
                severity=str(item.get("severity", "warning")),
                blocking=bool(item.get("blocking", False)),
                message=str(item.get("message", "")),
                element_id=item.get("element_id"),
                page_number=item.get("page_number"),
                details=dict(item.get("details") or {}),
            )
            for item in quality_raw.get("issues", [])
        ]
        try:
            status = QualityStatus(quality_raw.get("status", "review"))
            unknown_status = False
        except ValueError:
            status = QualityStatus.BLOCKED
            unknown_status = True
        if unknown_status:
            issues.append(
                QualityIssue(
                    code="unknown_quality_status",
                    severity="error",
                    blocking=True,
                    message="Stored quality status is not recognized; manual review is required.",
                    details={"stored_status": quality_raw.get("status")},
                )
            )
        report = QualityReport(
            status=status,
            issues=issues,
            metrics=dict(quality_raw.get("metrics") or {}),
            generated_by=str(quality_raw.get("generated_by", "deterministic_rules_v1")),
        )
        return cls(
            parsed_document=parsed,
            cleaned_document=cleaned,
            chunks=chunks,
            quality_report=report,
            document_type=DocumentType(payload.get("document_type", "general")),
            chunk_strategy=str(payload.get("chunk_strategy", "unknown")),
        )

    def to_documents(self):
        """Rebuild vector documents from this artifact without invoking a parser."""

        from .adapter import LangChainDocumentAdapter

        return LangChainDocumentAdapter().to_documents(
            self.chunks,
            document=self.cleaned_document,
            document_type=self.document_type,
            chunk_strategy=self.chunk_strategy,
        )


def to_primitive(value: Any) -> Any:
    """Convert typed structures recursively to JSON-safe primitives."""

    if isinstance(value, StrEnum):
        return value.value
    if is_dataclass(value):
        return {item.name: to_primitive(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, dict):
        return {str(key): to_primitive(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [to_primitive(item) for item in value]
    if isinstance(value, bytes):
        raise TypeError("asset bytes cannot be embedded in a JSON ingestion artifact")
    return value


def parsed_document_to_dict(document: ParsedDocument) -> dict[str, Any]:
    return to_primitive(document)


def parsed_document_from_dict(payload: dict[str, Any]) -> ParsedDocument:
    elements = [element_from_dict(item) for item in payload.get("elements", [])]
    return ParsedDocument(
        document_id=str(payload.get("document_id", "")),
        file_name=str(payload.get("file_name", "")),
        elements=elements,
        parser=str(payload.get("parser", "unknown")),
        source_type=str(payload.get("source_type", "unknown")),
        metadata=dict(payload.get("metadata") or {}),
        parser_version=str(payload.get("parser_version", "unknown")),
        parser_config=dict(payload.get("parser_config") or {}),
    )


def element_from_dict(payload: dict[str, Any]) -> ParsedElement:
    table_raw = payload.get("structured_table")
    table = None
    if table_raw:
        table = StructuredTable(
            rows=[list(row) for row in table_raw.get("rows", [])],
            cells=[TableCell(**cell) for cell in table_raw.get("cells", [])],
            header_rows=int(table_raw.get("header_rows", 0)),
            units=list(table_raw.get("units", [])),
            notes=list(table_raw.get("notes", [])),
            caption=table_raw.get("caption"),
            structure_source=str(table_raw.get("structure_source", "unknown")),
            metadata=dict(table_raw.get("metadata") or {}),
        )
    provenance = tuple(
        SourceProvenance(
            page_number=item.get("page_number"),
            bbox=tuple(item["bbox"]) if item.get("bbox") is not None else None,
            page_width=item.get("page_width"),
            page_height=item.get("page_height"),
            coordinate_origin=CoordinateOrigin(item.get("coordinate_origin", "unknown")),
            source_region=item.get("source_region"),
        )
        for item in payload.get("provenance", [])
    )
    assets = tuple(AssetReference(**item) for item in payload.get("asset_refs", []))
    return ParsedElement(
        element_id=str(payload.get("element_id", "")),
        element_type=ElementType(payload.get("element_type", "paragraph")),
        text=str(payload.get("text", payload.get("search_text", "")) or ""),
        page_number=payload.get("page_number"),
        heading_level=payload.get("heading_level"),
        section_path=tuple(payload.get("section_path", [])),
        metadata=dict(payload.get("metadata") or {}),
        raw_text=payload.get("raw_text"),
        search_text=payload.get("search_text"),
        reading_order=payload.get("reading_order"),
        provenance=provenance,
        confidence=payload.get("confidence"),
        structured_table=table,
        asset_refs=assets,
    )


def chunk_from_dict(payload: dict[str, Any]) -> Chunk:
    provenance = tuple(
        SourceProvenance(
            page_number=item.get("page_number"),
            bbox=tuple(item["bbox"]) if item.get("bbox") is not None else None,
            page_width=item.get("page_width"),
            page_height=item.get("page_height"),
            coordinate_origin=CoordinateOrigin(item.get("coordinate_origin", "unknown")),
            source_region=item.get("source_region"),
        )
        for item in payload.get("source_locations", [])
    )
    return Chunk(
        text=str(payload.get("text", "")),
        element_ids=tuple(payload.get("element_ids", [])),
        page_numbers=tuple(payload.get("page_numbers", [])),
        section_path=tuple(payload.get("section_path", [])),
        metadata=dict(payload.get("metadata") or {}),
        source_locations=provenance,
        asset_refs=tuple(AssetReference(**item) for item in payload.get("asset_refs", [])),
    )
