package com.wenrun.ai.vo;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import lombok.Data;

/**
 * FastAPI SSE 事件：{@code {"type":"token","content":"..."}} 或 {@code {"type":"done","reply":"..."}}。
 */
@Data
@JsonIgnoreProperties(ignoreUnknown = true)
public class ChatStreamEventVO {

    /** status | token | done | error */
    private String type;

    private String content;

    private String reply;

    private String conversationId;
}
