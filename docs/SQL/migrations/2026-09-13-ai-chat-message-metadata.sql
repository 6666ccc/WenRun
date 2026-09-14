ALTER TABLE chat_messages
  ADD COLUMN metadata_json JSON NULL COMMENT 'SSE确认状态等可恢复UI元数据' AFTER content;
