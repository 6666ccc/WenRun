package com.wenrun.ai.security;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;

import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.Base64;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

class DelegatedToolAuthInterceptorTest {

    private final DelegationTokenService tokenService = new DelegationTokenService(
            Base64.getEncoder().encodeToString("01234567890123456789012345678901".getBytes(StandardCharsets.UTF_8)),
            Duration.ofMinutes(5));
    private final DelegatedToolAuthInterceptor interceptor = new DelegatedToolAuthInterceptor(tokenService);

    @AfterEach
    void cleanContext() {
        DelegatedToolContext.clear();
    }

    @Test
    void acceptsDelegatedBearerTokenAndCreatesScopedContext() {
        MockHttpServletRequest request = new MockHttpServletRequest();
        String token = tokenService.issue(7L, "patient", 11L, Set.of("departments:read"));
        request.addHeader("Authorization", "Bearer " + token);

        interceptor.preHandle(request, new MockHttpServletResponse(), new Object());

        assertEquals(7L, DelegatedToolContext.getRequired().userId());
        assertEquals(11L, DelegatedToolContext.getRequired().patientId());
        assertEquals(true, DelegatedToolContext.getRequired().hasScope("departments:read"));
    }

    @Test
    void rejectsRequestWithoutBearerToken() {
        assertThrows(Exception.class,
                () -> interceptor.preHandle(new MockHttpServletRequest(), new MockHttpServletResponse(), new Object()));
    }
}
