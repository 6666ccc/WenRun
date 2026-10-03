CREATE TABLE `ai_conversations` (
  `user_id` bigint NOT NULL COMMENT '会话所有者用户ID',
  `conversation_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '用户作用域内的会话ID',
  `patient_id` bigint NOT NULL COMMENT '当前会话讨论的患者ID，对应 patient.id；会话内不可切换',
  `status` varchar(24) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'active' COMMENT 'active',
  `version` bigint NOT NULL DEFAULT '0' COMMENT '会话状态乐观版本',
  `create_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `deleted_time` datetime DEFAULT NULL COMMENT '软删除时间',
  PRIMARY KEY (`user_id`,`conversation_id`),
  KEY `idx_ai_conversations_update_time` (`update_time`),
  KEY `idx_ai_conversations_user_patient_update` (`user_id`,`patient_id`,`update_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='AI会话归属';
