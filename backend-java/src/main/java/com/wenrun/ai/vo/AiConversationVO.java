package com.wenrun.ai.vo;

import lombok.Data;

import java.time.LocalDateTime;

@Data
public class AiConversationVO {
    private String conversationId;
    private String title;
    private String lastMessage;
    private Long messageCount;
    private LocalDateTime updateTime;
}
