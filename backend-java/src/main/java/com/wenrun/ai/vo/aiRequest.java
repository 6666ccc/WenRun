package com.wenrun.ai.vo;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import lombok.Data;

@Data
public class aiRequest {

    @NotBlank(message = "消息不能为空")
    @Size(max = 2000, message = "消息长度不能超过 2000 个字符")
    private String message;

    @Size(max = 64, message = "会话 ID 长度不能超过 64 个字符")
    private String conversationId;

    /**
     * 是否允许 Python AI 服务使用会话记忆；未传时由 Python 服务使用默认值。
     */
    private Boolean memoryEnabled;
}
