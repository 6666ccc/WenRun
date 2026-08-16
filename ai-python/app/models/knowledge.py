from pydantic import ConfigDict, Field

from app.models.chat import ApiModel


class IngestResponse(ApiModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    document_id: str = Field(alias="documentId")
    knowledge_base: str = Field(alias="knowledgeBase")
    chunk_count: int = Field(alias="chunkCount")
