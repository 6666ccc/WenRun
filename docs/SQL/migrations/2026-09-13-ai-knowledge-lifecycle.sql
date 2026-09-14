-- R3: versioned, effective-dated RAG document registry.
-- Run once after the base schema. Existing READY rows become active version 1.
ALTER TABLE ai_knowledge_documents
  DROP INDEX uk_ai_knowledge_document_id,
  ADD COLUMN version INT NOT NULL DEFAULT 1 AFTER document_id,
  ADD COLUMN effective_from DATETIME NULL AFTER status,
  ADD COLUMN expires_at DATETIME NULL AFTER effective_from,
  ADD COLUMN qdrant_sync_status VARCHAR(24) NOT NULL DEFAULT 'synced' AFTER chunk_count,
  ADD COLUMN operation_id VARCHAR(64) NULL AFTER qdrant_sync_status,
  ADD UNIQUE KEY uk_ai_knowledge_document_revision (document_id, version),
  ADD KEY idx_ai_knowledge_effective
    (knowledge_base, status, effective_from, expires_at),
  ADD KEY idx_ai_knowledge_operation (operation_id);

UPDATE ai_knowledge_documents
SET qdrant_sync_status = CASE
      WHEN status IN ('FAILED', 'DELETE_FAILED') THEN 'reconcile_required'
      ELSE 'synced'
    END,
    status = CASE
      WHEN status = 'READY' THEN 'active'
      WHEN status IN ('DELETING', 'DELETE_FAILED') THEN 'inactive'
      WHEN status = 'DELETED' THEN 'deleted'
      ELSE LOWER(status)
    END,
    effective_from = COALESCE(effective_from, completed_at, created_at);
