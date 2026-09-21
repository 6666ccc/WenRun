package com.wenrun.entity;

import lombok.Data;

import java.time.LocalDateTime;

@Data
public class ChatMessage {
    private Long id;
    private String conversationId;
    /** 会话所有者账号 ID。conversation_id 仅在该账号作用域内唯一，因此消息必须带 user_id；患者主体以 ai_conversations.patient_id 为准。 */
    private Long userId;
    private String clientRequestId;
    private String role;
    private String content;
    private String metadataJson;
    private LocalDateTime createTime;
}
