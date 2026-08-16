package com.wenrun.ai.tools.dto;

public record AiToolRegistrationCreateDTO(
        Long patientId,
        Long scheduleId,
        String idempotencyKey,
        String interruptId
) {
}
