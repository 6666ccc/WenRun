from pydantic import Field

from app.models.chat import ApiModel


class CitationSource(ApiModel):
    id: str
    document_id: str = Field(alias="documentId")
    title: str
    page: int | None = None
    section: str | None = None
    excerpt: str


class ToolSource(ApiModel):
    tool_name: str = Field(alias="toolName")
    query_time: str = Field(alias="queryTime")
    summary: str
