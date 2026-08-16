package com.wenrun.ai.tools.interceptor;

import com.wenrun.ai.delegation.AiDelegationClaims;
import com.wenrun.ai.delegation.AiDelegationException;
import com.wenrun.ai.delegation.AiDelegationProperties;
import com.wenrun.ai.delegation.AiDelegationTokenService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

class DelegatedJwtInterceptorTest {

    private AiDelegationTokenService tokenService;
    private DelegatedJwtInterceptor interceptor;

    @BeforeEach
    void setUp() {
        AiDelegationProperties properties = new AiDelegationProperties();
        properties.setSecret("test-ai-delegation-secret-key-32!!");
        properties.setExpirySeconds(300);
        tokenService = new AiDelegationTokenService(properties);
        interceptor = new DelegatedJwtInterceptor(tokenService);
    }

    @Test
    void acceptsValidDelegationTokenAndStoresClaims() throws Exception {
        String token = tokenService.issueReadToken(1L, 10L, "c-1");
        MockHttpServletRequest request = new MockHttpServletRequest("GET", "/api/internal/ai-tools/depts");
        request.addHeader("Authorization", "Bearer " + token);

        assertTrue(interceptor.preHandle(request, new MockHttpServletResponse(), new Object()));
        AiDelegationClaims claims = (AiDelegationClaims) request.getAttribute(DelegatedJwtInterceptor.CLAIMS_ATTR);
        assertEquals(10L, claims.patientId());
        assertEquals("c-1", claims.conversationId());
    }

    @Test
    void rejectsMissingToken() {
        MockHttpServletRequest request = new MockHttpServletRequest("GET", "/api/internal/ai-tools/depts");
        assertThrows(AiDelegationException.class,
                () -> interceptor.preHandle(request, new MockHttpServletResponse(), new Object()));
    }

    @Test
    void rejectsApiKeyInPlaceOfDelegationToken() {
        MockHttpServletRequest request = new MockHttpServletRequest("GET", "/api/internal/ai-tools/depts");
        request.addHeader("X-Api-Key", "internal");
        assertThrows(AiDelegationException.class,
                () -> interceptor.preHandle(request, new MockHttpServletResponse(), new Object()));
    }
}
