-- MySQL 8. Existing client_request_id + role is the stable message key.
-- Run against the intended application database before deploying this change.
SET @has_summary_json = (SELECT COUNT(*) FROM information_schema.columns
  WHERE table_schema = DATABASE() AND table_name = 'ai_conversations' AND column_name = 'summary_json');
SET @summary_ddl = IF(@has_summary_json = 0,
  'ALTER TABLE ai_conversations ADD COLUMN summary_json JSON NULL', 'SELECT 1');
PREPARE summary_stmt FROM @summary_ddl;
EXECUTE summary_stmt;
DEALLOCATE PREPARE summary_stmt;

SET @has_summary_version = (SELECT COUNT(*) FROM information_schema.columns
  WHERE table_schema = DATABASE() AND table_name = 'ai_conversations' AND column_name = 'summary_version');
SET @summary_ddl = IF(@has_summary_version = 0,
  'ALTER TABLE ai_conversations ADD COLUMN summary_version BIGINT NOT NULL DEFAULT 0', 'SELECT 1');
PREPARE summary_stmt FROM @summary_ddl;
EXECUTE summary_stmt;
DEALLOCATE PREPARE summary_stmt;
