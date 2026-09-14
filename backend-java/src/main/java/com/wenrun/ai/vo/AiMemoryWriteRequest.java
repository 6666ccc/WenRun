package com.wenrun.ai.vo;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;
import lombok.Data;

import java.time.LocalDateTime;

@Data
public class AiMemoryWriteRequest {
    @NotBlank
    @Pattern(regexp = "communication_preference|appointment_preference|accessibility_need")
    private String type;

    @NotBlank
    @Size(max = 500)
    private String content;

    @Size(max = 64)
    private String sourceConversationId;

    private Long sourceMessageId;
    private LocalDateTime expireTime;
    private Integer expectedVersion;
}
