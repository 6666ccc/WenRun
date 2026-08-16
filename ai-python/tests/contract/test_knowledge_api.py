import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.knowledge import IngestResponse
from app.rag.collections import KnowledgeBase


class FakeKnowledgeOps:
    def ingest_document(self, file, document_id, base, original_name):
        value = base.value if isinstance(base, KnowledgeBase) else base
        return IngestResponse(
            document_id=document_id,
            knowledge_base=value,
            chunk_count=12,
        )

    def delete_document(self, base, document_id):
        return None


@pytest.fixture
def knowledge_client():
    from app.api.routes.knowledge import get_knowledge_ops

    app.dependency_overrides[get_knowledge_ops] = lambda: FakeKnowledgeOps()
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_knowledge_ops, None)


def test_knowledge_ingest_requires_api_key():
    client = TestClient(app)
    response = client.post(
        "/v1/knowledge/ingest",
        data={
            "documentId": "doc-1",
            "knowledgeBase": "medical-general",
            "originalName": "guide.pdf",
        },
        files={"file": ("guide.pdf", b"%PDF-1.4", "application/pdf")},
    )
    assert response.status_code == 401


def test_knowledge_ingest_response_shape(knowledge_client):
    response = knowledge_client.post(
        "/v1/knowledge/ingest",
        headers={"X-Api-Key": "test-internal-api-key"},
        data={
            "documentId": "doc-1",
            "knowledgeBase": "medical-general",
            "originalName": "guide.pdf",
        },
        files={"file": ("guide.pdf", b"%PDF-1.4", "application/pdf")},
    )
    assert response.status_code == 200
    assert response.json() == {
        "documentId": "doc-1",
        "knowledgeBase": "medical-general",
        "chunkCount": 12,
    }


def test_knowledge_delete_is_idempotent(knowledge_client):
    headers = {"X-Api-Key": "test-internal-api-key"}
    first = knowledge_client.delete("/v1/knowledge/medical-general/doc-1", headers=headers)
    second = knowledge_client.delete("/v1/knowledge/medical-general/doc-1", headers=headers)
    assert first.status_code == 204
    assert second.status_code == 204
