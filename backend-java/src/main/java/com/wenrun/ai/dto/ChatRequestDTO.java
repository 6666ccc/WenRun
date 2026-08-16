package com.wenrun.ai.dto;

import jakarta.validation.constraints.NotBlank;
import lombok.Data;

@Data
public class ChatRequestDTO {

    @NotBlank(message = "消息不能为空")
    private String message;

    @NotBlank(message = "会话标识不能为空")
    private String conversationId;

    private Boolean memoryEnabled;
}
