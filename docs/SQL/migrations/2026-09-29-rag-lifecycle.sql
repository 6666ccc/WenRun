-- 知识库提交、解析、审核和发布登记。
-- 时间列保存 UTC ISO-8601 文本，与 Python 生命周期代码的写入格式一致。
-- 在已有 wenrun 库上执行一次。新环境直接使用 schema.sql 即可。

USE wenrun;

SET NAMES utf8mb4;

SELECT DATABASE() AS target_database;

CREATE TABLE IF NOT EXISTS rag_documents (
  document_id     VARCHAR(64)  NOT NULL COMMENT '逻辑文档ID',
  latest_version  INT          NOT NULL DEFAULT 0 COMMENT '已分配的最大版本号',
  created_by      VARCHAR(64)  NOT NULL COMMENT '创建人',
  created_at      VARCHAR(40)  NOT NULL COMMENT '创建时间，UTC ISO-8601',
  deleted_at      VARCHAR(40)  DEFAULT NULL COMMENT '删除时间，UTC ISO-8601',
  PRIMARY KEY (document_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='知识库逻辑文档';

CREATE TABLE IF NOT EXISTS rag_versions (
  document_id     VARCHAR(64)  NOT NULL COMMENT '逻辑文档ID',
  version         INT          NOT NULL COMMENT '版本号',
  source_asset_id VARCHAR(64)  NOT NULL COMMENT '原文件资产ID',
  source_name     VARCHAR(255) NOT NULL COMMENT '原始文件名',
  checksum        VARCHAR(64)  NOT NULL COMMENT '原文件SHA-256',
  file_size       BIGINT       NOT NULL COMMENT '原文件字节数',
  scope           VARCHAR(16)  NOT NULL COMMENT 'public或staff',
  metadata_json   LONGTEXT     NOT NULL COMMENT '上传元数据JSON',
  effective_from  VARCHAR(40)  NOT NULL COMMENT '生效时间，UTC ISO-8601',
  expires_at      VARCHAR(40)  DEFAULT NULL COMMENT '失效时间，UTC ISO-8601',
  status          VARCHAR(32)  NOT NULL COMMENT 'queued/needs_review/approved/active/scheduled/rejected/failed',
  active_build_id VARCHAR(64)  DEFAULT NULL COMMENT '当前发布使用的构建ID',
  created_by      VARCHAR(64)  NOT NULL COMMENT '创建人',
  created_at      VARCHAR(40)  NOT NULL COMMENT '创建时间，UTC ISO-8601',
  PRIMARY KEY (document_id, version),
  KEY idx_rag_versions_status (document_id, status, effective_from, expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='知识库文档版本';

CREATE TABLE IF NOT EXISTS rag_builds (
  build_id               VARCHAR(64)  NOT NULL COMMENT '构建ID',
  document_id            VARCHAR(64)  NOT NULL COMMENT '逻辑文档ID',
  version                INT          NOT NULL COMMENT '版本号',
  status                 VARCHAR(32)  NOT NULL COMMENT '构建状态',
  artifact_asset_id      VARCHAR(64)  DEFAULT NULL COMMENT '解析产物资产ID',
  parser_fingerprint     VARCHAR(255) DEFAULT NULL COMMENT '解析器指纹',
  embedding_fingerprint  VARCHAR(255) DEFAULT NULL COMMENT '向量模型指纹',
  quality_json           LONGTEXT     DEFAULT NULL COMMENT '质量报告JSON',
  chunk_count            INT          NOT NULL DEFAULT 0 COMMENT '检索片段数',
  created_at             VARCHAR(40)  NOT NULL COMMENT '创建时间，UTC ISO-8601',
  updated_at             VARCHAR(40)  NOT NULL COMMENT '更新时间，UTC ISO-8601',
  PRIMARY KEY (build_id),
  KEY idx_rag_builds_version (document_id, version)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='知识库解析构建';

CREATE TABLE IF NOT EXISTS rag_jobs (
  job_id            VARCHAR(64)  NOT NULL COMMENT '任务ID',
  document_id       VARCHAR(64)  NOT NULL COMMENT '逻辑文档ID',
  version           INT          NOT NULL COMMENT '版本号',
  build_id          VARCHAR(64)  NOT NULL COMMENT '构建ID',
  source_asset_id   VARCHAR(64)  NOT NULL COMMENT '原文件资产ID',
  status            VARCHAR(32)  NOT NULL COMMENT 'queued/running/succeeded/needs_review/failed/retry_wait/cancelled',
  attempts          INT          NOT NULL DEFAULT 0 COMMENT '已尝试次数',
  max_attempts      INT          NOT NULL DEFAULT 3 COMMENT '最大尝试次数',
  available_at      VARCHAR(40)  NOT NULL COMMENT '可领取时间，UTC ISO-8601',
  lease_owner       VARCHAR(128) DEFAULT NULL COMMENT '当前工人',
  lease_until       VARCHAR(40)  DEFAULT NULL COMMENT '租约到期，UTC ISO-8601',
  fence             INT          NOT NULL DEFAULT 0 COMMENT '租约代数',
  error_code        VARCHAR(80)  DEFAULT NULL COMMENT '最近一次错误类型',
  created_at        VARCHAR(40)  NOT NULL COMMENT '创建时间，UTC ISO-8601',
  updated_at        VARCHAR(40)  NOT NULL COMMENT '更新时间，UTC ISO-8601',
  PRIMARY KEY (job_id),
  KEY idx_rag_jobs_ready (status, available_at, lease_until)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='知识库解析任务';

CREATE TABLE IF NOT EXISTS rag_assets (
  asset_id      VARCHAR(64)  NOT NULL COMMENT '资产ID',
  storage_key   VARCHAR(255) NOT NULL COMMENT '对象存储键',
  file_name     VARCHAR(255) NOT NULL COMMENT '文件名',
  content_type  VARCHAR(128) NOT NULL COMMENT 'MIME类型',
  file_size     BIGINT       NOT NULL COMMENT '字节数',
  checksum      VARCHAR(64)  NOT NULL COMMENT 'SHA-256',
  document_id   VARCHAR(64)  NOT NULL COMMENT '逻辑文档ID',
  version       INT          NOT NULL COMMENT '版本号',
  build_id      VARCHAR(64)  DEFAULT NULL COMMENT '构建ID',
  kind          VARCHAR(32)  NOT NULL COMMENT 'source或artifact',
  scope         VARCHAR(16)  NOT NULL COMMENT 'public或staff',
  created_by    VARCHAR(64)  NOT NULL COMMENT '创建人',
  created_at    VARCHAR(40)  NOT NULL COMMENT '创建时间，UTC ISO-8601',
  PRIMARY KEY (asset_id),
  UNIQUE KEY uk_rag_assets_storage_key (storage_key),
  KEY idx_rag_assets_doc (document_id, version, kind)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='知识库原文件与解析产物';

CREATE TABLE IF NOT EXISTS rag_audit (
  id            BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
  document_id   VARCHAR(64)  NOT NULL COMMENT '逻辑文档ID',
  version       INT          DEFAULT NULL COMMENT '版本号',
  build_id      VARCHAR(64)  DEFAULT NULL COMMENT '构建ID',
  actor_id      VARCHAR(64)  NOT NULL COMMENT '操作人',
  action        VARCHAR(32)  NOT NULL COMMENT 'submit/parsed/approve/reject/retry/publish',
  reason        VARCHAR(2000) DEFAULT NULL COMMENT '审核意见',
  details_json  LONGTEXT     NOT NULL COMMENT '操作详情JSON',
  created_at    VARCHAR(40)  NOT NULL COMMENT '创建时间，UTC ISO-8601',
  PRIMARY KEY (id),
  KEY idx_rag_audit_document (document_id, version)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='知识库发布审计';
