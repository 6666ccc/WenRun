"""Durable authority for RAG jobs, revisions, builds, assets, and publication.

SQLite is a persistent development backend. Production must use MySQL; in
particular, a missing MySQL connection is never treated as an empty registry.
"""

from __future__ import annotations

import json
import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pymysql

from app.core.config import get_settings


class LeaseLost(RuntimeError):
    """The worker no longer owns the job, so artifact writes must roll back."""


class LifecycleRepository:
    def __init__(self, *, backend: str, sqlite_path: str | None = None):
        self.backend = backend
        self.sqlite_path = sqlite_path

    @classmethod
    def from_environment(cls) -> LifecycleRepository:
        settings = get_settings()
        backend = os.getenv("RAG_DATABASE_BACKEND", "").strip().lower()
        environment = os.getenv("RAG_ENVIRONMENT", "development").lower()
        if not backend:
            backend = "mysql" if settings.rag_metadata_mysql_host else "sqlite"
        if environment == "production" and backend != "mysql":
            raise RuntimeError("RAG_ENVIRONMENT=production requires RAG_DATABASE_BACKEND=mysql")
        if backend == "mysql":
            if not settings.rag_metadata_mysql_host or not settings.rag_metadata_mysql_user:
                raise RuntimeError("RAG MySQL authority is not configured")
            return cls(backend="mysql")
        if backend != "sqlite":
            raise RuntimeError("RAG_DATABASE_BACKEND must be mysql or sqlite")
        path = os.getenv("RAG_SQLITE_PATH", "data/rag-lifecycle.sqlite3")
        path_obj = Path(path).expanduser()
        if not path_obj.is_absolute():
            path_obj = Path(__file__).resolve().parents[2] / path_obj
        path_obj.parent.mkdir(parents=True, exist_ok=True)
        return cls(backend="sqlite", sqlite_path=str(path_obj.resolve()))

    @contextmanager
    def connection(self, *, write: bool = False) -> Iterator[Any]:
        if self.backend == "sqlite":
            connection = sqlite3.connect(self.sqlite_path, timeout=30, isolation_level=None)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA busy_timeout=30000")
            try:
                connection.execute("BEGIN IMMEDIATE" if write else "BEGIN")
                yield connection
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                connection.close()
            return

        settings = get_settings()
        connection = pymysql.connect(
            host=settings.rag_metadata_mysql_host,
            port=settings.rag_metadata_mysql_port,
            user=settings.rag_metadata_mysql_user,
            password=settings.rag_metadata_mysql_password,
            database=settings.rag_metadata_mysql_database,
            charset="utf8mb4",
            autocommit=False,
            connect_timeout=5,
            read_timeout=20,
            write_timeout=20,
            cursorclass=pymysql.cursors.DictCursor,
        )
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _sql(self, sql: str) -> str:
        return sql.replace("?", "%s") if self.backend == "mysql" else sql

    def _execute(self, cursor: Any, sql: str, params: tuple = ()) -> Any:
        cursor.execute(self._sql(sql), params)
        return cursor

    @staticmethod
    def _dict(row: Any) -> dict | None:
        if row is None:
            return None
        return dict(row)

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)

    @staticmethod
    def _load(value: Any, default: Any = None) -> Any:
        if value is None:
            return default
        if isinstance(value, (dict, list)):
            return value
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return default

    def initialize(self) -> None:
        """Create only the local development schema; MySQL uses checked-in migrations."""
        if self.backend != "sqlite":
            return
        statements = [
            """CREATE TABLE IF NOT EXISTS rag_documents (
                document_id TEXT PRIMARY KEY, latest_version INTEGER NOT NULL DEFAULT 0,
                created_by TEXT NOT NULL, created_at TEXT NOT NULL, deleted_at TEXT)""",
            """CREATE TABLE IF NOT EXISTS rag_versions (
                document_id TEXT NOT NULL, version INTEGER NOT NULL,
                source_asset_id TEXT NOT NULL, source_name TEXT NOT NULL,
                checksum TEXT NOT NULL, file_size INTEGER NOT NULL,
                scope TEXT NOT NULL CHECK(scope IN ('public','staff')),
                metadata_json TEXT NOT NULL, effective_from TEXT NOT NULL,
                expires_at TEXT, status TEXT NOT NULL, active_build_id TEXT,
                created_by TEXT NOT NULL, created_at TEXT NOT NULL,
                PRIMARY KEY(document_id, version),
                FOREIGN KEY(document_id) REFERENCES rag_documents(document_id))""",
            """CREATE TABLE IF NOT EXISTS rag_builds (
                build_id TEXT PRIMARY KEY, document_id TEXT NOT NULL,
                version INTEGER NOT NULL, status TEXT NOT NULL,
                artifact_asset_id TEXT, parser_fingerprint TEXT,
                embedding_fingerprint TEXT, quality_json TEXT,
                chunk_count INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(document_id,version) REFERENCES rag_versions(document_id,version))""",
            """CREATE TABLE IF NOT EXISTS rag_jobs (
                job_id TEXT PRIMARY KEY, document_id TEXT NOT NULL, version INTEGER NOT NULL,
                build_id TEXT NOT NULL, source_asset_id TEXT NOT NULL, status TEXT NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0, max_attempts INTEGER NOT NULL DEFAULT 3,
                available_at TEXT NOT NULL, lease_owner TEXT, lease_until TEXT,
                fence INTEGER NOT NULL DEFAULT 0, error_code TEXT, created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(build_id) REFERENCES rag_builds(build_id))""",
            """CREATE TABLE IF NOT EXISTS rag_assets (
                asset_id TEXT PRIMARY KEY, storage_key TEXT NOT NULL UNIQUE,
                file_name TEXT NOT NULL, content_type TEXT NOT NULL,
                file_size INTEGER NOT NULL, checksum TEXT NOT NULL,
                document_id TEXT NOT NULL, version INTEGER NOT NULL,
                build_id TEXT, kind TEXT NOT NULL, scope TEXT NOT NULL,
                created_by TEXT NOT NULL, created_at TEXT NOT NULL)""",
            """CREATE TABLE IF NOT EXISTS rag_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT, document_id TEXT NOT NULL,
                version INTEGER, build_id TEXT, actor_id TEXT NOT NULL,
                action TEXT NOT NULL, reason TEXT, details_json TEXT NOT NULL,
                created_at TEXT NOT NULL)""",
            "CREATE INDEX IF NOT EXISTS idx_rag_jobs_ready ON rag_jobs(status,available_at,lease_until)",
            "CREATE INDEX IF NOT EXISTS idx_rag_versions_status ON rag_versions(document_id,status,effective_from,expires_at)",
            "CREATE INDEX IF NOT EXISTS idx_rag_assets_doc ON rag_assets(document_id,version,kind)",
        ]
        with self.connection(write=True) as connection:
            for statement in statements:
                connection.execute(statement)

    def create_submission(
        self, *, document_id: str, version: int, build_id: str, job_id: str,
        source_asset: dict, scope: str, metadata: dict, effective_from: str,
        expires_at: str | None, actor_id: str, force_rebuild: bool,
    ) -> dict:
        now = datetime.now(UTC).isoformat()
        with self.connection(write=True) as connection:
            cursor = connection.cursor()
            self._execute(cursor,
                "INSERT INTO rag_assets(asset_id,storage_key,file_name,content_type,file_size,checksum,document_id,version,build_id,kind,scope,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (source_asset["asset_id"], source_asset["storage_key"], source_asset["file_name"],
                 source_asset["content_type"], source_asset["file_size"], source_asset["checksum"],
                 document_id, version, build_id, "source", scope, actor_id, now))
            if self.backend == "mysql":
                self._execute(cursor, "INSERT IGNORE INTO rag_documents(document_id,latest_version,created_by,created_at) VALUES(?,?,?,?)", (document_id, max(0, version), actor_id, now))
                self._execute(cursor, "SELECT latest_version FROM rag_documents WHERE document_id=? FOR UPDATE", (document_id,))
                doc = cursor.fetchone()
                if doc is None:
                    raise RuntimeError("document reservation failed")
                current_version = int(doc["latest_version"])
            else:
                self._execute(cursor, "INSERT OR IGNORE INTO rag_documents(document_id,latest_version,created_by,created_at) VALUES(?,?,?,?)", (document_id, 0, actor_id, now))
                self._execute(cursor, "SELECT latest_version FROM rag_documents WHERE document_id=?", (document_id,))
                current_version = int(cursor.fetchone()["latest_version"])
            if version == 0:
                version = current_version + 1
            elif force_rebuild and version != current_version:
                raise RuntimeError("a rebuild must target the current document revision")
            elif not force_rebuild and version != current_version + 1:
                raise RuntimeError("document revision changed while upload was being queued")
            # Source asset insertion precedes revision allocation, so update its reserved version here.
            self._execute(cursor, "UPDATE rag_assets SET version=? WHERE asset_id=?", (version, source_asset["asset_id"]))
            if not force_rebuild:
                self._execute(cursor,
                    "INSERT INTO rag_versions(document_id,version,source_asset_id,source_name,checksum,file_size,scope,metadata_json,effective_from,expires_at,status,active_build_id,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (document_id, version, source_asset["asset_id"], source_asset["file_name"],
                     source_asset["checksum"], source_asset["file_size"], scope,
                     self._json(metadata), effective_from, expires_at, "queued", None, actor_id, now))
            self._execute(cursor,
                "INSERT INTO rag_builds(build_id,document_id,version,status,created_at,updated_at) VALUES(?,?,?,?,?,?)",
                (build_id, document_id, version, "queued", now, now))
            self._execute(cursor,
                "INSERT INTO rag_jobs(job_id,document_id,version,build_id,source_asset_id,status,available_at,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
                (job_id, document_id, version, build_id, source_asset["asset_id"], "queued", now, now, now))
            self._execute(cursor, "UPDATE rag_documents SET latest_version=? WHERE document_id=?", (max(current_version, version), document_id))
            self._audit(cursor, document_id, version, build_id, actor_id, "submit", None, {"scope": scope})
            return {"document_id": document_id, "version": version, "build_id": build_id, "job_id": job_id, "status": "queued"}

    def _audit(self, cursor: Any, document_id: str, version: int | None, build_id: str | None,
               actor_id: str, action: str, reason: str | None, details: dict) -> None:
        self._execute(cursor,
            "INSERT INTO rag_audit(document_id,version,build_id,actor_id,action,reason,details_json,created_at) VALUES(?,?,?,?,?,?,?,?)",
            (document_id, version, build_id, actor_id, action, reason, self._json(details), datetime.now(UTC).isoformat()))

    def find_duplicate(self, *, checksum: str, scope: str, document_id: str | None = None) -> dict | None:
        with self.connection() as connection:
            cursor = connection.cursor()
            sql = "SELECT v.*, b.build_id, j.job_id FROM rag_versions v LEFT JOIN rag_builds b ON b.build_id=v.active_build_id LEFT JOIN rag_jobs j ON j.build_id=b.build_id WHERE v.checksum=? AND v.scope=? AND v.status NOT IN ('deleted','rejected','failed')"
            params: tuple = (checksum, scope)
            if document_id:
                sql += " AND v.document_id=?"
                params += (document_id,)
            sql += " ORDER BY v.version DESC LIMIT 1"
            self._execute(cursor, sql, params)
            return self._dict(cursor.fetchone())


    def get_latest(self, document_id: str) -> dict | None:
        with self.connection() as connection:
            cursor = connection.cursor()
            self._execute(cursor, "SELECT * FROM rag_versions WHERE document_id=? ORDER BY version DESC LIMIT 1", (document_id,))
            return self._dict(cursor.fetchone())

    def asset(self, asset_id: str) -> dict | None:
        with self.connection() as connection:
            cursor = connection.cursor()
            self._execute(cursor, "SELECT * FROM rag_assets WHERE asset_id=?", (asset_id,))
            return self._dict(cursor.fetchone())

    def register_artifact(self, *, asset: dict, build_id: str, quality: dict,
                          parser_fingerprint: str, embedding_fingerprint: str,
                          chunk_count: int, quality_state: str, job_id: str, fence: int,
                          worker_id: str) -> bool:
        now = datetime.now(UTC).isoformat()
        with self.connection(write=True) as connection:
            cursor = connection.cursor()
            lock_suffix = " FOR UPDATE" if self.backend == "mysql" else ""
            self._execute(cursor, "SELECT document_id,version FROM rag_builds WHERE build_id=?" + lock_suffix, (build_id,))
            build_identity = cursor.fetchone()
            if not build_identity:
                return False
            self._execute(cursor, "SELECT scope,created_by FROM rag_versions WHERE document_id=? AND version=?" + lock_suffix, (build_identity["document_id"], build_identity["version"]))
            version_identity = cursor.fetchone()
            if not version_identity:
                return False
            row = {**dict(build_identity), **dict(version_identity)}
            self._execute(cursor, "SELECT status,fence,lease_owner,lease_until FROM rag_jobs WHERE job_id=?" + lock_suffix, (job_id,))
            job = cursor.fetchone()
            if (not job or job["status"] != "running" or int(job["fence"]) != fence
                    or job["lease_owner"] != worker_id or not job["lease_until"]
                    or job["lease_until"] <= now):
                return False
            self._execute(cursor,
                "INSERT INTO rag_assets(asset_id,storage_key,file_name,content_type,file_size,checksum,document_id,version,build_id,kind,scope,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (asset["asset_id"], asset["storage_key"], asset["file_name"], asset["content_type"],
                 asset["file_size"], asset["checksum"], row["document_id"], row["version"], build_id,
                 "artifact", row["scope"], row["created_by"], now))
            state = "needs_review" if quality_state == "needs_review" else "built"
            self._execute(cursor,
                "UPDATE rag_builds SET status=?,artifact_asset_id=?,parser_fingerprint=?,embedding_fingerprint=?,quality_json=?,chunk_count=?,updated_at=? WHERE build_id=?",
                (state, asset["asset_id"], parser_fingerprint, embedding_fingerprint, self._json(quality), chunk_count, now, build_id))
            version_state = "needs_review" if quality_state == "needs_review" else "approved"
            self._execute(cursor, "UPDATE rag_versions SET status=? WHERE document_id=? AND version=?", (version_state, row["document_id"], row["version"]))
            job_state = "needs_review" if quality_state == "needs_review" else "succeeded"
            updated = self._execute(cursor, "UPDATE rag_jobs SET status=?,lease_owner=NULL,lease_until=NULL,updated_at=? WHERE job_id=? AND fence=? AND status='running' AND lease_owner=? AND lease_until>?", (job_state, now, job_id, fence, worker_id, now))
            if updated.rowcount != 1:
                raise LeaseLost(job_id)
            self._audit(cursor, row["document_id"], int(row["version"]), build_id, row["created_by"], "parsed", None, {"quality_state": quality_state, "chunk_count": chunk_count})
            return True

    def fail_job(self, *, job_id: str, fence: int, worker_id: str, error_code: str,
                 retry_delay_seconds: int = 0) -> bool:
        now = datetime.now(UTC)
        now_text = now.isoformat()
        with self.connection(write=True) as connection:
            cursor = connection.cursor()
            lock_suffix = " FOR UPDATE" if self.backend == "mysql" else ""
            self._execute(cursor, "SELECT * FROM rag_jobs WHERE job_id=?" + lock_suffix, (job_id,))
            job = cursor.fetchone()
            if (not job or job["status"] != "running" or int(job["fence"]) != fence
                    or job["lease_owner"] != worker_id or not job["lease_until"]
                    or job["lease_until"] <= now_text):
                return False
            exhausted = int(job["attempts"]) >= int(job["max_attempts"])
            status = "failed" if exhausted else "retry_wait"
            available = (now + timedelta(seconds=retry_delay_seconds)).isoformat()
            self._execute(cursor, "UPDATE rag_jobs SET status=?,error_code=?,available_at=?,lease_owner=NULL,lease_until=NULL,updated_at=? WHERE job_id=? AND fence=?", (status, error_code[:80], available, now_text, job_id, fence))
            if exhausted:
                self._execute(cursor, "UPDATE rag_builds SET status='failed',updated_at=? WHERE build_id=?", (now_text, job["build_id"]))
                self._execute(cursor, "UPDATE rag_versions SET status='failed' WHERE document_id=? AND version=? AND status<>'active'", (job["document_id"], job["version"]))
            return True

    def claim_job(self, worker_id: str, *, lease_seconds: int) -> dict | None:
        now = datetime.now(UTC)
        now_text = now.isoformat()
        until = (now + timedelta(seconds=lease_seconds)).isoformat()
        with self.connection(write=True) as connection:
            cursor = connection.cursor()
            lock_suffix = " FOR UPDATE SKIP LOCKED" if self.backend == "mysql" else ""
            self._execute(cursor, "SELECT * FROM rag_jobs WHERE status='running' AND lease_until<? AND attempts>=max_attempts LIMIT 32" + lock_suffix, (now_text,))
            for exhausted in cursor.fetchall():
                self._execute(cursor, "UPDATE rag_jobs SET status='failed',lease_owner=NULL,lease_until=NULL,error_code='worker_lease_exhausted',updated_at=? WHERE job_id=? AND fence=?", (now_text, exhausted["job_id"], exhausted["fence"]))
                self._execute(cursor, "UPDATE rag_builds SET status='failed',updated_at=? WHERE build_id=?", (now_text, exhausted["build_id"]))
                self._execute(cursor, "UPDATE rag_versions SET status='failed' WHERE document_id=? AND version=? AND status='queued'", (exhausted["document_id"], exhausted["version"]))
            if self.backend == "mysql":
                self._execute(cursor, "SELECT * FROM rag_jobs WHERE attempts<max_attempts AND ((status IN ('queued','retry_wait') AND available_at<=?) OR (status='running' AND lease_until<?)) ORDER BY created_at LIMIT 1 FOR UPDATE SKIP LOCKED", (now_text, now_text))
            else:
                self._execute(cursor, "SELECT * FROM rag_jobs WHERE attempts<max_attempts AND ((status IN ('queued','retry_wait') AND available_at<=?) OR (status='running' AND lease_until<?)) ORDER BY created_at LIMIT 1", (now_text, now_text))
            job = self._dict(cursor.fetchone())
            if not job:
                return None
            fence = int(job["fence"]) + 1
            self._execute(cursor, "UPDATE rag_jobs SET status='running',attempts=attempts+1,lease_owner=?,lease_until=?,fence=?,updated_at=? WHERE job_id=?", (worker_id, until, fence, now_text, job["job_id"]))
            job["status"] = "running"
            job["attempts"] = int(job["attempts"]) + 1
            job["fence"] = fence
            job["lease_owner"] = worker_id
            job["lease_until"] = until
            self._execute(cursor, "SELECT a.*,v.metadata_json,v.effective_from,v.expires_at,v.scope,v.source_name FROM rag_assets a JOIN rag_versions v ON v.document_id=? AND v.version=? WHERE a.asset_id=?", (job["document_id"], job["version"], job["source_asset_id"],))
            job["source"] = self._dict(cursor.fetchone())
            return job


    def get_job(self, job_id: str) -> dict | None:
        with self.connection() as connection:
            cursor = connection.cursor()
            self._execute(cursor, "SELECT * FROM rag_jobs WHERE job_id=?", (job_id,))
            row = self._dict(cursor.fetchone())
            if row:
                self._execute(cursor, "SELECT status AS build_status,quality_json,chunk_count,artifact_asset_id FROM rag_builds WHERE build_id=?", (row["build_id"],))
                build = self._dict(cursor.fetchone()) or {}
                row.update(build)
            return row

    def get_document(self, document_id: str) -> dict:
        with self.connection() as connection:
            cursor = connection.cursor()
            self._execute(cursor, "SELECT * FROM rag_versions WHERE document_id=? ORDER BY version DESC", (document_id,))
            versions = [self._dict(row) for row in cursor.fetchall()]
            for version in versions:
                version["metadata"] = self._load(version.pop("metadata_json", None), {})
                self._execute(cursor, "SELECT * FROM rag_builds WHERE document_id=? AND version=? ORDER BY created_at DESC", (document_id, version["version"]))
                version["builds"] = []
                for build in cursor.fetchall():
                    item = self._dict(build)
                    item["quality_report"] = self._load(item.pop("quality_json", None), None)
                    version["builds"].append(item)
                self._execute(cursor, "SELECT * FROM rag_audit WHERE document_id=? AND version=? ORDER BY id", (document_id, version["version"]))
                version["audit"] = []
                for audit in cursor.fetchall():
                    item = self._dict(audit)
                    item["details"] = self._load(item.pop("details_json", None), {})
                    version["audit"].append(item)
            return {"document_id": document_id, "versions": versions}

    def list_documents(self, *, page: int, page_size: int, scope: str | None = None) -> dict:
        offset = (page - 1) * page_size
        with self.connection() as connection:
            cursor = connection.cursor()
            where, params = ("", ()) if scope is None else ("WHERE scope=?", (scope,))
            self._execute(cursor, f"SELECT COUNT(DISTINCT document_id) AS total FROM rag_versions {where}", params)
            total = int(cursor.fetchone()["total"])
            self._execute(cursor, f"SELECT v.* FROM rag_versions v JOIN (SELECT document_id,MAX(version) AS version FROM rag_versions {where} GROUP BY document_id) latest USING(document_id,version) ORDER BY created_at DESC LIMIT ? OFFSET ?", params + (page_size, offset))
            items = [self._dict(row) for row in cursor.fetchall()]
            return {"items": items, "page": page, "page_size": page_size, "total": total}

    def decision(self, document_id: str, version: int, *, decision: str, actor_id: str,
                 reason: str, build_id: str | None = None) -> dict:
        now = datetime.now(UTC).isoformat()
        with self.connection(write=True) as connection:
            cursor = connection.cursor()
            self._execute(cursor, "SELECT * FROM rag_versions WHERE document_id=? AND version=?", (document_id, version))
            row = self._dict(cursor.fetchone())
            if not row:
                raise KeyError(document_id)
            if decision == "approve" and row["status"] != "needs_review":
                raise ValueError("only a needs_review version can be approved")
            if decision == "reject" and row["status"] not in {"needs_review", "queued", "failed"}:
                raise ValueError("this version cannot be rejected")
            if decision == "approve":
                self._execute(cursor, "SELECT quality_json,build_id,status FROM rag_builds WHERE document_id=? AND version=? ORDER BY created_at DESC LIMIT 1" + (" FOR UPDATE" if self.backend == "mysql" else ""), (document_id, version))
                build = self._dict(cursor.fetchone())
                report = self._load(build.get("quality_json") if build else None, {})
                issues = report.get("issues", []) if isinstance(report, dict) else []
                blocked = (report.get("status") == "blocked" or report.get("publish_blocked") is True
                           or report.get("can_publish") is False
                           or any(isinstance(issue, dict) and issue.get("blocking") for issue in issues))
                if blocked:
                    raise ValueError("quality report blocks publication; repair or reparse the source")
                state = "approved"
                self._execute(cursor, "UPDATE rag_versions SET status=? WHERE document_id=? AND version=?", (state, document_id, version))
                if build:
                    self._execute(cursor, "UPDATE rag_builds SET status='approved',updated_at=? WHERE build_id=?", (now, build["build_id"]))
                    build_id = build["build_id"]
            else:
                state = "rejected"
                self._execute(cursor, "UPDATE rag_versions SET status='rejected' WHERE document_id=? AND version=?", (document_id, version))
                self._execute(cursor, "UPDATE rag_builds SET status='rejected',updated_at=? WHERE document_id=? AND version=?", (now, document_id, version))
                self._execute(cursor, "UPDATE rag_jobs SET status='cancelled',fence=fence+1,lease_owner=NULL,lease_until=NULL,updated_at=? WHERE document_id=? AND version=? AND status IN ('queued','retry_wait','running')", (now, document_id, version))
            self._audit(cursor, document_id, version, build_id, actor_id, decision, reason, {"quality_report_unchanged": True})
            return {"document_id": document_id, "version": version, "build_id": build_id, "status": state}

    def retry_job(self, job_id: str, actor_id: str) -> dict:
        now = datetime.now(UTC).isoformat()
        with self.connection(write=True) as connection:
            cursor = connection.cursor()
            self._execute(cursor, "SELECT * FROM rag_jobs WHERE job_id=?" + (" FOR UPDATE" if self.backend == "mysql" else ""), (job_id,))
            job = self._dict(cursor.fetchone())
            if not job:
                raise KeyError(job_id)
            if job["status"] != "failed":
                raise ValueError("only failed jobs can be retried; review required jobs must be approved or rejected")
            self._execute(cursor, "UPDATE rag_jobs SET status='queued',attempts=0,available_at=?,lease_owner=NULL,lease_until=NULL,error_code=NULL,updated_at=? WHERE job_id=?", (now, now, job_id))
            self._execute(cursor, "UPDATE rag_builds SET status='queued',updated_at=? WHERE build_id=?", (now, job["build_id"]))
            self._execute(cursor, "UPDATE rag_versions SET status='queued' WHERE document_id=? AND version=? AND status='failed'", (job["document_id"], job["version"]))
            self._audit(cursor, job["document_id"], int(job["version"]), job["build_id"], actor_id, "retry", None, {})
            return {**job, "status": "queued"}

    def publish(self, document_id: str, version: int, actor_id: str) -> dict:
        now = datetime.now(UTC)
        with self.connection(write=True) as connection:
            cursor = connection.cursor()
            lock_suffix = " FOR UPDATE" if self.backend == "mysql" else ""
            self._execute(cursor, "SELECT * FROM rag_versions WHERE document_id=? AND version=?" + lock_suffix, (document_id, version))
            row = self._dict(cursor.fetchone())
            if not row:
                raise KeyError(document_id)
            if row["status"] not in {"approved", "built", "scheduled"}:
                raise ValueError("only approved builds can be published")
            if row["status"] == "scheduled" and row["effective_from"] > now.isoformat():
                raise ValueError("scheduled revision is not effective yet")
            if self.backend == "mysql":
                self._execute(cursor, "SELECT version,effective_from,status FROM rag_versions WHERE document_id=? AND active_build_id IS NOT NULL AND status='scheduled' FOR UPDATE", (document_id,))
            else:
                self._execute(cursor, "SELECT version,effective_from,status FROM rag_versions WHERE document_id=? AND active_build_id IS NOT NULL AND status='scheduled'", (document_id,))
            future = [self._dict(item) for item in cursor.fetchall()]
            future_newer = [item for item in future if int(item["version"]) > version and item["effective_from"] > now.isoformat()]
            if future_newer and row["effective_from"] <= now.isoformat():
                raise ValueError("a newer future revision is already scheduled")
            if not row["active_build_id"]:
                # build may exist without pointer until this authority commit
                self._execute(cursor, "SELECT * FROM rag_builds WHERE document_id=? AND version=? AND status IN ('built','approved') ORDER BY created_at DESC LIMIT 1", (document_id, version))
                build = self._dict(cursor.fetchone())
                if not build or not build["artifact_asset_id"]:
                    raise ValueError("build artifact is incomplete")
                build_id = build["build_id"]
            else:
                build_id = row["active_build_id"]
            effective = datetime.fromisoformat(row["effective_from"])
            if effective.tzinfo is None:
                effective = effective.replace(tzinfo=UTC)
            state = "scheduled" if effective > now else "active"
            if state == "active":
                self._execute(cursor, "UPDATE rag_versions SET status='superseded' WHERE document_id=? AND status='active' AND version<?", (document_id, version))
            self._execute(cursor, "UPDATE rag_versions SET status=?,active_build_id=? WHERE document_id=? AND version=?", (state, build_id, document_id, version))
            self._execute(cursor, "UPDATE rag_builds SET status=? WHERE build_id=?", (state, build_id))
            self._audit(cursor, document_id, version, build_id, actor_id, "publish", None, {"status": state})
            return {"document_id": document_id, "version": version, "build_id": build_id, "status": state}

    def authority_rows(self, scopes: tuple[str, ...], *, now: datetime | None = None) -> list[dict]:
        if not scopes:
            return []
        current = (now or datetime.now(UTC)).astimezone(UTC).isoformat()
        with self.connection() as connection:
            cursor = connection.cursor()
            sql = """SELECT v.document_id,v.version,v.scope,v.effective_from,v.expires_at,v.status,
                      b.build_id,b.status AS build_status
                   FROM rag_versions v JOIN rag_builds b ON b.build_id=v.active_build_id
                   WHERE v.status IN ('active','scheduled','inactive','superseded')
                     AND v.effective_from<=? AND b.status IN ('active','scheduled','inactive','superseded')"""
            self._execute(cursor, sql, (current,))
            candidates = [self._dict(row) for row in cursor.fetchall()]
        latest: dict[str, dict] = {}
        for row in candidates:
            prior = latest.get(row["document_id"])
            if prior is None or (row["effective_from"], int(row["version"])) > (prior["effective_from"], int(prior["version"])):
                latest[row["document_id"]] = row
        # Resolve one winning published revision per document before applying scope,
        # status, or expiry. Otherwise a private, expired, or deactivated replacement
        # could accidentally reveal an older public revision again.
        result = []
        for row in latest.values():
            expires = datetime.fromisoformat(row["expires_at"]) if row.get("expires_at") else None
            if expires is not None and expires.tzinfo is None:
                expires = expires.replace(tzinfo=UTC)
            if row["scope"] not in scopes or row["status"] not in {"active", "scheduled"}:
                continue
            if expires is not None and expires <= (now or datetime.now(UTC)).astimezone(UTC):
                continue
            result.append(row)
        return result
