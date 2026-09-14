package com.wenrun.entity;

import lombok.Data;

import java.time.LocalDateTime;

/** AI 会话的权威归属记录；conversationId 只在单个用户作用域内唯一。 */
@Data
public class AiConversation {
    private Long userId;
    private String conversationId;
    private Long patientId;
    private String status;
    private Long version;
    private LocalDateTime createTime;
    private LocalDateTime updateTime;
    private LocalDateTime deletedTime;
}
