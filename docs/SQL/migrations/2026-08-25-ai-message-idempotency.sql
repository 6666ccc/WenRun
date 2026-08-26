-- 为 AI 对话轮次增加客户端幂等键。
-- 旧消息的 client_request_id 保持 NULL；MySQL 对唯一索引中的 NULL 允许多行，兼容历史数据。
ALTER TABLE chat_messages
  ADD COLUMN client_request_id VARCHAR(64) NULL COMMENT '客户端对话轮次幂等键' AFTER user_id;

ALTER TABLE chat_messages
  ADD UNIQUE KEY uk_chat_messages_client_request
    (user_id, conversation_id, client_request_id, role);
