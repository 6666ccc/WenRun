package com.wenrun.ai.logging;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class AiLogSanitizerTest {

    @Test
    void redactsServiceHeadersAndBearerTokens() {
        String cleaned = AiLogSanitizer.redact(
                "X-Api-Key: super-secret Authorization: Bearer jwt-token X-Delegated-Token: delegated");
        assertFalse(cleaned.contains("super-secret"));
        assertFalse(cleaned.contains("jwt-token"));
        assertFalse(cleaned.contains("delegated"));
        assertTrue(cleaned.contains("X-Api-Key=[redacted]"));
    }
}
