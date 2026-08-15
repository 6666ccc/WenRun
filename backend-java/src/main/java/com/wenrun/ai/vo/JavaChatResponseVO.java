package com.wenrun.ai.vo;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Data;

/**
 * Python {@code POST /java/chat} 的响应体。
 * 字段名与 FastAPI 返回的 snake_case JSON 对齐。
 */
@Data
public class JavaChatResponseVO {

    @JsonProperty("user_input")
    private String userInput;

    private String intent;

    @JsonProperty("target_agent")
    private String targetAgent;

    private Double confidence;

    private String reasoning;

    @JsonProperty("final_output")
    private String finalOutput;

    @JsonProperty("session_id")
    private String sessionId;
}
