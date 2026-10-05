-- Manual preferences do not originate in a chat. Preserve historical provenance.
-- Repeatable; apply before enabling manual creation. No rows are removed.
ALTER TABLE ai_patient_memories
  MODIFY COLUMN source_conversation_id VARCHAR(64) NULL,
  MODIFY COLUMN source_message_id BIGINT NULL;
