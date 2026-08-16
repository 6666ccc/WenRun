from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status

from app.api.dependencies.auth import verify_api_key
from app.models.knowledge import IngestResponse
from app.rag.collections import KnowledgeBase
from app.rag.ingest import delete_document, ingest_document


router = APIRouter(
    prefix="/v1/knowledge",
    tags=["Knowledge"],
    dependencies=[Depends(verify_api_key)],
)


class KnowledgeOps:
    def ingest_document(self, file, document_id: str, base: KnowledgeBase, original_name: str):
        return ingest_document(file, document_id, base, original_name)

    def delete_document(self, base: KnowledgeBase, document_id: str) -> None:
        delete_document(base, document_id)


def get_knowledge_ops() -> KnowledgeOps:
    return KnowledgeOps()


@router.post("/ingest", response_model=IngestResponse)
async def ingest(
    file: UploadFile = File(...),
    documentId: str = Form(...),
    knowledgeBase: str = Form(...),
    originalName: str = Form(...),
    ops: KnowledgeOps = Depends(get_knowledge_ops),
) -> IngestResponse:
    base = _parse_knowledge_base(knowledgeBase)
    try:
        return ops.ingest_document(file.file, documentId, base, originalName)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete(
    "/{knowledgeBase}/{documentId}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_knowledge_document(
    knowledgeBase: str,
    documentId: str,
    ops: KnowledgeOps = Depends(get_knowledge_ops),
) -> Response:
    base = _parse_knowledge_base(knowledgeBase)
    ops.delete_document(base, documentId)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _parse_knowledge_base(value: str) -> KnowledgeBase:
    try:
        return KnowledgeBase(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="unsupported knowledgeBase") from exc
