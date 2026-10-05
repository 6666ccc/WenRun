CREATE TABLE `ai_patient_memories` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '修订记录主键',
  `memory_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '跨修订稳定的记忆ID',
  `patient_id` bigint NOT NULL COMMENT '患者ID',
  `type` varchar(40) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '受控记忆类型',
  `content` varchar(500) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '患者明确声明的偏好',
  `source_conversation_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '来源会话',
  `source_message_id` bigint NOT NULL COMMENT '来源用户消息',
  `status` varchar(24) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'active' COMMENT 'pending/active/superseded/deleted',
  `version` int NOT NULL DEFAULT '1' COMMENT '修订版本',
  `confidence` decimal(5,4) NOT NULL DEFAULT '1.0000' COMMENT '显式声明默认1',
  `expire_time` datetime DEFAULT NULL COMMENT '过期时间',
  `create_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `deleted_time` datetime DEFAULT NULL COMMENT '删除时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_ai_patient_memory_revision` (`memory_id`,`version`),
  KEY `idx_ai_patient_memory_active` (`patient_id`,`status`,`expire_time`,`update_time`)
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='受治理的AI患者偏好记忆及版本';
