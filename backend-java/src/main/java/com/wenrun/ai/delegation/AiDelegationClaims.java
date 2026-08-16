package com.wenrun.ai.delegation;

import java.util.List;

public record AiDelegationClaims(
        Long userId,
        Long patientId,
        String conversationId,
        List<String> scopes,
        String interruptId,
        String jwtId
) {
}
