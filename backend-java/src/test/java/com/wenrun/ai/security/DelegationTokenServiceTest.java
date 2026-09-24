package com.wenrun.ai.security;

import com.wenrun.common.exception.BusinessException;
import org.junit.jupiter.api.Test;

import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.Base64;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

class DelegationTokenServiceTest {

    private final DelegationTokenService service = new DelegationTokenService(
            Base64.getEncoder().encodeToString("01234567890123456789012345678901".getBytes(StandardCharsets.UTF_8)),
            Duration.ofMinutes(5));

    @Test
    void issuedTokenCanBeVerifiedForToolApi() {
        String token = service.issue(7L, "patient", 11L,
                Set.of("departments:read", "schedules:read"));

        DelegatedToolPrincipal principal = service.verifyForToolApi(token);

        assertEquals(7L, principal.userId());
        assertEquals(11L, principal.patientId());
        assertEquals("patient", principal.accountType());
        assertTrue(principal.hasScope("departments:read"));
        assertFalse(principal.hasScope("registrations:create"));
    }

    @Test
    void modifiedTokenIsRejected() {
        String token = service.issue(7L, "patient", 11L, Set.of("departments:read"));

        assertThrows(BusinessException.class,
                () -> service.verifyForToolApi(token + "modified"));
    }

    @Test
    void patientAssistantScopesCoverReadsAndRegistrationWrites() {
        assertEquals(
                Set.of("departments:read", "schedules:read", "staff:read",
                        "registrations:read", "registrations:write",
                        "memories:read", "memories:write", "clinical:read"),
                DelegationTokenService.PATIENT_ASSISTANT_SCOPES);
    }
}
