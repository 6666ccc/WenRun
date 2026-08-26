package com.wenrun.entity;

import lombok.Data;

import java.time.LocalDateTime;

@Data
public class ChatMessage {
    private Long id;
    private String conversationId;
    private Long userId;
    private String clientRequestId;
    private String role;
    private String content;
    private LocalDateTime createTime;
}
