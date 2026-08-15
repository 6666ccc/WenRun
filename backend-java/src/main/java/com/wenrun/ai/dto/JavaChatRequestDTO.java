package com.wenrun.ai.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.Map;

/**
 * 调用 Python {@code POST /java/chat} 的请求体，
 * 对应 FastAPI 的 {@code JavaChatRequest} Pydantic 模型。
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class JavaChatRequestDTO {

    /** 用户输入文本 */
    private String content;

    /** 用户 ID（可选） */
    private String userId;

    /** 会话 ID（可选，对应 Java 端 conversationId） */
    private String sessionId;

    /** 扩展字段（可选） */
    private Map<String, Object> extra;
}
