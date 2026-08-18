package com.wenrun.config;

import com.wenrun.common.ResultCode;
import com.wenrun.common.constant.AccountType;
import com.wenrun.common.context.UserContext;
import com.wenrun.common.exception.BusinessException;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * 覆盖当前 AuthInterceptor：患者 UUID Token 校验、OPTIONS 放行；API Key 不能绕过。
 */
class AuthInterceptorTest {

    private static final String API_KEY = "test-api-key";

    private AuthTokenStore authTokenStore;
    private AuthInterceptor interceptor;

    @BeforeEach
    void setUp() {
        authTokenStore = new AuthTokenStore();
        interceptor = new AuthInterceptor(authTokenStore);
    }

    @AfterEach
    void clearContext() {
        UserContext.clear();
    }

    @Test
    void allowsOptionsWithoutAuth() throws Exception {
        MockHttpServletRequest request = new MockHttpServletRequest("OPTIONS", "/api/ai/chat");
        assertTrue(interceptor.preHandle(request, new MockHttpServletResponse(), new Object()));
    }

    @Test
    void rejectsApiKeyForPatientApi() {
        MockHttpServletRequest request = new MockHttpServletRequest("GET", "/api/patients");
        request.addHeader("X-Api-Key", API_KEY);
        request.addHeader("X-User-Id", "42");

        BusinessException exception = assertThrows(BusinessException.class,
                () -> interceptor.preHandle(request, new MockHttpServletResponse(), new Object()));

        assertEquals(ResultCode.UNAUTHORIZED, exception.getCode());
    }

    @Test
    void allowsValidToken() throws Exception {
        String token = authTokenStore.createToken(7L, AccountType.PATIENT);
        MockHttpServletRequest request = new MockHttpServletRequest("GET", "/api/patients");
        request.addHeader("Authorization", "Bearer " + token);

        assertTrue(interceptor.preHandle(request, new MockHttpServletResponse(), new Object()));
        assertEquals(7L, UserContext.getUserId());
        assertEquals(AccountType.PATIENT, UserContext.getAccountType());
    }

    @Test
    void rejectsMissingToken() {
        MockHttpServletRequest request = new MockHttpServletRequest("GET", "/api/patients");

        BusinessException exception = assertThrows(BusinessException.class,
                () -> interceptor.preHandle(request, new MockHttpServletResponse(), new Object()));

        assertEquals(ResultCode.UNAUTHORIZED, exception.getCode());
    }

    @Test
    void rejectsUnknownToken() {
        MockHttpServletRequest request = new MockHttpServletRequest("GET", "/api/patients");
        request.addHeader("X-Token", "not-a-real-token");

        BusinessException exception = assertThrows(BusinessException.class,
                () -> interceptor.preHandle(request, new MockHttpServletResponse(), new Object()));

        assertEquals(ResultCode.UNAUTHORIZED, exception.getCode());
    }
}
