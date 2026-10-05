"""知识库提交、解析和发布不依赖真实向量服务。"""

import re
from datetime import UTC, datetime, timedelta

import pytest

from app.rag.ingestion import IngestionService, NativeDocumentParser
from app.rag.lifecycle import RagLifecycleService, RagNotFoundError
from app.rag.lifecycle_repository import LifecycleRepository
from app.rag.lifecycle_storage import LocalAssetStorage


class _OfflineTokenizer:
    _parts = re.compile(r"[A-Za-z0-9]+|[\u3400-\u9fff]|[^\s]")

    def encode(self, text, **kwargs):
        return self._parts.findall(text)

    def decode(self, tokens, **kwargs):
        return "".join(tokens)


def _service(tmp_path):
    repository = LifecycleRepository(backend="sqlite", sqlite_path=str(tmp_path / "life.sqlite3"))
    repository.initialize()
    written = {}
    status_calls = []

    def index_documents(documents, ids=None):
        written["documents"] = documents
        written["ids"] = list(ids or [])
        return written["ids"]

    def set_status(document_id, status, **kwargs):
        status_calls.append((document_id, status, kwargs.get("version")))

    service = RagLifecycleService(
        repository=repository,
        storage=LocalAssetStorage(str(tmp_path / "assets")),
        ingestion=IngestionService(parser=NativeDocumentParser(), tokenizer=_OfflineTokenizer()),
        index_documents=index_documents,
        set_status=set_status,
        delete_points=lambda *args, **kwargs: None,
        worker_id="test-worker",
    )
    return service, written, status_calls


def test_submit_parse_and_publish_without_calling_embeddings(tmp_path):
    service, written, status_calls = _service(tmp_path)
    actor = {"id": 7, "admin": True, "scopes": ("knowledge:manage",)}
    content = "# 门诊服务\n\n## 挂号流程\n\n请携带身份证在自助机挂号。\n".encode()

    receipt = service.submit(content, "门诊指南.md", actor=actor, scope="public")

    assert receipt["status"] == "queued"
    assert receipt["idempotent"] is False
    assert service.process_once() is True
    job = service.get_job(receipt["job_id"], actor=actor)
    assert job["status"] == "succeeded"
    assert job["quality_report"]["status"] == "pass"
    document = service.get_document(receipt["document_id"], actor=actor)
    assert document["versions"][0]["status"] == "approved"

    published = service.publish(receipt["document_id"], receipt["version"], actor=actor)

    assert published["status"] == "active"
    assert written["ids"]
    assert written["documents"][0].metadata["status"] == "pending"
    assert (receipt["document_id"], "active", receipt["version"]) in status_calls
    assert written["documents"][0].metadata["scope"] == "public"
    assert "挂号流程" in written["documents"][0].metadata["section_path"]
    again = service.submit(content, "门诊指南.md", actor=actor, scope="public")
    assert again["idempotent"] is True
    assert again["version"] == receipt["version"]
    source_id = document["versions"][0]["source_asset_id"]
    body, name, content_type = service.read_asset(source_id, actor=actor)
    assert body == content
    assert name == "门诊指南.md"
    assert content_type == "text/markdown"
    try:
        service.read_asset(source_id, actor={"id": 3, "scopes": ()})
    except RagNotFoundError:
        denied = True
    else:
        denied = False
    assert denied
    visible, _, _ = service.read_asset(
        source_id, actor={"id": 3, "scopes": ("knowledge:public",)},
    )
    assert visible == content
    listed = service.list_documents(page=1, page_size=20, scope="public", actor=actor)
    assert listed["total"] == 1
    assert listed["items"][0]["status"] == "active"


def test_future_source_stays_hidden_from_patients(tmp_path):
    service, written, status_calls = _service(tmp_path)
    actor = {"id": 7, "admin": True, "scopes": ("knowledge:manage",)}
    content = "# 门诊服务\n\n## 挂号流程\n\n明天开始执行的就诊说明。\n".encode()
    tomorrow = (datetime.now(UTC) + timedelta(days=1)).isoformat()

    receipt = service.submit(
        content, "明日须知.md", actor=actor, scope="public", effective_from=tomorrow,
    )
    assert service.process_once() is True
    published = service.publish(receipt["document_id"], receipt["version"], actor=actor)

    assert published["status"] == "scheduled"
    assert written["documents"][0].metadata["status"] == "pending"
    assert (receipt["document_id"], "scheduled", receipt["version"]) in status_calls
    source_id = service.get_document(receipt["document_id"], actor=actor)["versions"][0]["source_asset_id"]
    with pytest.raises(RagNotFoundError):
        service.read_asset(source_id, actor={"id": 3, "scopes": ("knowledge:public",)})
    body, _, _ = service.read_asset(source_id, actor=actor)
    assert body == content


def test_scheduled_publication_activates_only_when_due_and_retries_index_failure(tmp_path):
    service, _, status_calls = _service(tmp_path)
    actor = {"id": 7, "admin": True, "scopes": ("knowledge:manage",)}
    receipt = service.submit(
        "# 门诊\n\n## 就诊\n\n请按预约时间到院。".encode(), "due.md", actor=actor,
        effective_from=(datetime.now(UTC) + timedelta(days=1)).isoformat(),
    )
    assert service.process_once()
    service.publish(receipt["document_id"], receipt["version"], actor=actor)
    assert service.activate_due_publications() == 0
    # Move the recorded effective time, not the global clock.
    with service.repository.connection(write=True) as connection:
        service.repository._execute(connection.cursor(),
            "UPDATE rag_versions SET effective_from=? WHERE document_id=?",
            ((datetime.now(UTC) - timedelta(seconds=1)).isoformat(), receipt["document_id"]),
        )
    original = service.set_status
    service.set_status = lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("index down"))
    assert service.activate_due_publications() == 0
    assert service.get_document(receipt["document_id"], actor=actor)["versions"][0]["status"] == "scheduled"
    service.set_status = original
    assert service.activate_due_publications() == 1
    assert service.activate_due_publications() == 0
    assert (receipt["document_id"], "active", receipt["version"]) in status_calls
    assert service.get_document(receipt["document_id"], actor=actor)["versions"][0]["status"] == "active"
    source_id = service.get_document(receipt["document_id"], actor=actor)["versions"][0]["source_asset_id"]
    assert service.read_asset(source_id, actor={"id": 3, "scopes": ("knowledge:public",)})[0]


def test_due_replacement_supersedes_old_publication(tmp_path):
    service, _, status_calls = _service(tmp_path)
    actor = {"id": 7, "admin": True, "scopes": ("knowledge:manage",)}
    first = service.submit("# 门诊\n\n## 到院\n\n请提前到院。".encode(), "old.md", actor=actor)
    service.process_once()
    service.publish(first["document_id"], first["version"], actor=actor)
    replacement = service.submit(
        "# 门诊\n\n## 到院\n\n请按新时间到院。".encode(), "new.md", actor=actor,
        document_id=first["document_id"],
        effective_from=(datetime.now(UTC) + timedelta(days=1)).isoformat(),
    )
    service.process_once()
    service.publish(replacement["document_id"], replacement["version"], actor=actor)
    with service.repository.connection(write=True) as connection:
        service.repository._execute(connection.cursor(),
            "UPDATE rag_versions SET effective_from=? WHERE document_id=? AND version=?",
            ((datetime.now(UTC) - timedelta(microseconds=1)).isoformat(), replacement["document_id"], replacement["version"]),
        )
    assert service.activate_due_publications() == 1
    versions = {int(row["version"]): row for row in service.get_document(first["document_id"], actor=actor)["versions"]}
    assert versions[first["version"]]["status"] == "superseded"
    assert versions[replacement["version"]]["status"] == "active"
    assert (first["document_id"], "superseded", first["version"]) in status_calls
