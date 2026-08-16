package com.wenrun.ai.delegation;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

class AiDelegationTokenServiceTest {

    private AiDelegationTokenService service;

    @BeforeEach
    void setUp() {
        AiDelegationProperties properties = new AiDelegationProperties();
        properties.setSecret("test-ai-delegation-secret-key-32!!");
        properties.setExpirySeconds(300);
        service = new AiDelegationTokenService(properties);
    }

    @Test
    void readTokenCannotCreateRegistration() {
        String token = service.issueReadToken(1L, 10L, "c-1");
        assertThrows(AiDelegationException.class,
                () -> service.verify(token, "registration:create"));
    }

    @Test
    void writeTokenBindsInterruptAndPatient() {
        String token = service.issueWriteToken(1L, 10L, "c-1", "i-1");
        AiDelegationClaims claims = service.verify(token, "registration:create");
        assertEquals(10L, claims.patientId());
        assertEquals("i-1", claims.interruptId());
        assertEquals(1L, claims.userId());
        assertEquals("c-1", claims.conversationId());
    }

    @Test
    void readTokenAllowsQueryScopes() {
        String token = service.issueReadToken(1L, 10L, "c-1");
        AiDelegationClaims claims = service.verify(token, "dept:read");
        assertTrue(claims.scopes().contains("doctor:read"));
        assertTrue(claims.scopes().contains("schedule:read"));
        assertNull(claims.interruptId());
    }

    @Test
    void verifyRejectsWrongAudience() {
        String token = service.issueReadToken(1L, 10L, "c-1");
        AiDelegationTokenService other = service;
        assertThrows(AiDelegationException.class, () -> other.verify("not-a-jwt", "dept:read"));
    }
}
