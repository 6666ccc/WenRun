-- AI 会话归属改为显式、用户作用域的权威记录。
CREATE TABLE IF NOT EXISTS ai_conversations (
  user_id          BIGINT       NOT NULL COMMENT '会话所有者用户ID',
  conversation_id  VARCHAR(64)  NOT NULL COMMENT '用户作用域内的会话ID',
  patient_id       BIGINT       NULL COMMENT '会话创建时绑定的患者ID',
  status           VARCHAR(24)  NOT NULL DEFAULT 'active' COMMENT 'active',
  version          BIGINT       NOT NULL DEFAULT 0 COMMENT '会话状态乐观版本',
  create_time      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  deleted_time     DATETIME     NULL COMMENT '软删除时间',
  PRIMARY KEY (user_id, conversation_id),
  KEY idx_ai_conversations_update_time (update_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='AI会话归属';

-- 兼容已存在的聊天历史。历史数据无法可靠反推出 patient_id，保持 NULL。
INSERT IGNORE INTO ai_conversations
  (user_id, conversation_id, patient_id, status, version, deleted_time)
SELECT DISTINCT user_id, conversation_id, NULL, 'active', 0, NULL
FROM chat_messages;

ALTER TABLE chat_messages
  ADD KEY idx_chat_messages_user_conversation_time
    (user_id, conversation_id, create_time, id);
