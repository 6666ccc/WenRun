CREATE TABLE IF NOT EXISTS ai_patient_memories (
  id                     BIGINT       NOT NULL AUTO_INCREMENT,
  memory_id              VARCHAR(64)  NOT NULL,
  patient_id             BIGINT       NOT NULL,
  type                   VARCHAR(40)  NOT NULL,
  content                VARCHAR(500) NOT NULL,
  source_conversation_id VARCHAR(64)  NOT NULL,
  source_message_id      BIGINT       NOT NULL,
  status                 VARCHAR(24)  NOT NULL DEFAULT 'active',
  version                INT          NOT NULL DEFAULT 1,
  confidence             DECIMAL(5,4) NOT NULL DEFAULT 1.0000,
  expire_time            DATETIME     NULL,
  create_time            DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  update_time            DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  deleted_time           DATETIME     NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uk_ai_patient_memory_revision (memory_id, version),
  KEY idx_ai_patient_memory_active (patient_id, status, expire_time, update_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='受治理的AI患者偏好记忆及版本';
