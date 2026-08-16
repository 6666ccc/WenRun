package com.wenrun.ai.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import lombok.Data;

import java.util.Map;

@Data
public class ChatResumeRequestDTO {

    @NotBlank
    private String conversationId;

    @NotBlank
    private String interruptId;

    @NotNull
    private Boolean approved;

    private Map<String, Object> params;
}
