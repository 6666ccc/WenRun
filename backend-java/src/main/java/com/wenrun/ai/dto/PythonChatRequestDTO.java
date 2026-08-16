package com.wenrun.ai.dto;

public record PythonChatRequestDTO(
        String message,
        String conversationId,
        Boolean memoryEnabled,
        AiUserContextDTO userContext
) {
}
