package com.wenrun.entity;

import lombok.Data;

import java.time.LocalDateTime;

/**
 * AI 对话消息实体，对应表 chat_messages。
 * <p>存储时间线上的纯文本消息（前端回显 & 审计），与 Qdrant 中的向量语义片段互补。</p>
 */
@Data
public class ChatMessage {

    private Long id;
    /** 会话ID，与传给AI服务的conversationId一致 */
    private String conversationId;
    /** 发送者用户ID */
    private Long userId;
    /** 角色: user / assistant */
    private String role;
    /** 消息纯文本 */
    private String content;
    /** 创建时间 */
    private LocalDateTime createTime;
}
