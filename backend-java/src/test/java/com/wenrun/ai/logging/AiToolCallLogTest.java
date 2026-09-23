package com.wenrun.ai.logging;

import com.wenrun.ai.security.DelegatedToolPrincipal;
import com.wenrun.config.RequestTrace;
import jakarta.servlet.http.HttpServlet;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockFilterChain;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class AiToolCallLogTest {

    @AfterEach
    void clearTrace() {
        RequestTrace.clear();
    }

    @Test
    void mapsPythonToolNamesFromInternalPaths() {
        assertEquals("list_departments",
                AiToolCallLog.resolveTool("GET", "/api/internal/ai-tools/departments"));
        assertEquals("get_department",
                AiToolCallLog.resolveTool("GET", "/api/internal/ai-tools/departments/3"));
        assertEquals("list_schedules",
                AiToolCallLog.resolveTool("GET", "/api/internal/ai-tools/schedules"));
        assertEquals("get_schedule",
                AiToolCallLog.resolveTool("GET", "/api/internal/ai-tools/schedules/9"));
        assertEquals("list_doctors",
                AiToolCallLog.resolveTool("GET", "/api/internal/ai-tools/staff"));
        assertEquals("get_staff",
                AiToolCallLog.resolveTool("GET", "/api/internal/ai-tools/staff/8"));
        assertEquals("list_my_registrations",
                AiToolCallLog.resolveTool("GET", "/api/internal/ai-tools/registrations"));
        assertEquals("list_my_pending_registrations",
                AiToolCallLog.resolveTool("GET", "/api/internal/ai-tools/registrations/pending"));
        assertEquals("create_registration",
                AiToolCallLog.resolveTool("POST", "/api/internal/ai-tools/registrations"));
        assertEquals("cancel_registration",
                AiToolCallLog.resolveTool("POST", "/api/internal/ai-tools/registrations/55/cancel"));
        assertEquals("remember_preference",
                AiToolCallLog.resolveTool("POST", "/api/internal/ai-tools/memories"));
        assertEquals("forget_preference",
                AiToolCallLog.resolveTool("DELETE", "/api/internal/ai-tools/memories/mem-1"));
        assertEquals("patient_clinical_context",
                AiToolCallLog.resolveTool("GET", "/api/internal/ai-tools/patient-clinical-context"));
    }

    @Test
    void clinicalContextResultAndIdentityValuesStayOutOfLogs() {
        String secretBody = "{\"idCard\":\"110101199003078515\",\"phone\":\"13800138000\","
                + "\"address\":\"北京市朝阳区某某路1号\",\"url\":\"https://bucket.cos.example.com/a.pdf?q-sign=abc\"}";

        assertEquals("[clinical-context-redacted]", AiToolCallLog.resultForLog(
                "/api/internal/ai-tools/patient-clinical-context", secretBody));

        String redacted = AiToolCallLog.redactSensitive(secretBody);
        assertTrue(!redacted.contains("110101199003078515"));
        assertTrue(!redacted.contains("13800138000"));
        assertTrue(!redacted.contains("某某路"));
        assertTrue(!redacted.contains("q-sign"));
        assertTrue(!redacted.contains("https://"));
    }

    @Test
    void truncatesLongPayloadsAndDropsSensitiveQueryKeys() {
        String huge = "x".repeat(AiToolCallLog.MAX_PAYLOAD_CHARS + 20);
        assertTrue(AiToolCallLog.truncate(huge).endsWith("...[truncated]"));

        MockHttpServletRequest request = new MockHttpServletRequest();
        request.setParameter("deptId", "1");
        request.setParameter("token", "should-not-appear");
        request.setParameter("authorization", "Bearer secret");
        String query = AiToolCallLog.queryParams(request);

        assertTrue(query.contains("deptId=1"));
        assertTrue(!query.contains("should-not-appear"));
        assertTrue(!query.toLowerCase().contains("bearer"));
    }

    @Test
    void identityAndRequestIdComeFromDelegatedContext() {
        MockHttpServletRequest request = new MockHttpServletRequest();
        request.addHeader(RequestTrace.HEADER_NAME, "trace-123");
        request.setAttribute(AiToolCallLog.PRINCIPAL_ATTR,
                new DelegatedToolPrincipal(7L, 11L, "patient", Set.of("schedules:read"), "token-1"));
        RequestTrace.set("trace-123");

        assertEquals("trace-123", AiToolCallLog.requestId(request));
        assertEquals("userId=7 patientId=11", AiToolCallLog.identity(request));
        assertEquals("path=schedules query={deptId=1} body={\"scheduleId\":9}",
                AiToolCallLog.params("schedules", "{deptId=1}", "{\"scheduleId\":9}"));
    }
}

class AiToolAccessFilterTest {

    @Test
    void copiesResponseBodyAfterLoggingToolCall() throws Exception {
        AiToolAccessFilter filter = new AiToolAccessFilter();
        MockHttpServletRequest request = new MockHttpServletRequest(
                "GET", "/api/internal/ai-tools/departments");
        request.setParameter("status", "1");
        request.setAttribute(AiToolCallLog.PRINCIPAL_ATTR,
                new DelegatedToolPrincipal(7L, 11L, "patient", Set.of("departments:read"), "token-1"));
        MockHttpServletResponse response = new MockHttpServletResponse();
        MockFilterChain chain = new MockFilterChain(new HttpServlet() {
            @Override
            protected void service(HttpServletRequest req, HttpServletResponse res) throws IOException {
                res.setStatus(200);
                res.setCharacterEncoding("UTF-8");
                res.setContentType("application/json;charset=UTF-8");
                res.getWriter().write("{\"code\":200,\"data\":[{\"id\":1,\"deptName\":\"内科\"}]}");
            }
        });

        filter.doFilter(request, response, chain);

        assertEquals(200, response.getStatus());
        assertTrue(response.getContentAsString(StandardCharsets.UTF_8).contains("内科"));
    }

    @Test
    void ignoresNonToolApiRequests() throws Exception {
        AiToolAccessFilter filter = new AiToolAccessFilter();
        MockHttpServletRequest request = new MockHttpServletRequest("GET", "/api/health");
        MockHttpServletResponse response = new MockHttpServletResponse();
        MockFilterChain chain = new MockFilterChain(new HttpServlet() {
            @Override
            protected void service(HttpServletRequest req, HttpServletResponse res) throws IOException {
                res.getWriter().write("ok");
            }
        });

        filter.doFilter(request, response, chain);

        assertEquals("ok", response.getContentAsString());
    }
}
