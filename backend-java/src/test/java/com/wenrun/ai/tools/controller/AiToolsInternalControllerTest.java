package com.wenrun.ai.tools.controller;

import com.wenrun.ai.delegation.AiDelegationClaims;
import com.wenrun.ai.exception.AiExceptionHandler;
import com.wenrun.ai.tools.dto.AiToolRegistrationCreateDTO;
import com.wenrun.ai.tools.exception.AiToolException;
import com.wenrun.ai.tools.interceptor.DelegatedJwtInterceptor;
import com.wenrun.ai.tools.service.AiToolsRegistrationService;
import com.wenrun.entity.Dept;
import com.wenrun.service.DeptService;
import com.wenrun.service.ScheduleService;
import com.wenrun.service.StaffService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import java.util.List;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@ExtendWith(MockitoExtension.class)
class AiToolsInternalControllerTest {

    @Mock
    private DeptService deptService;
    @Mock
    private StaffService staffService;
    @Mock
    private ScheduleService scheduleService;
    @Mock
    private AiToolsRegistrationService registrationService;

    private MockMvc mockMvc;

    @BeforeEach
    void setUp() {
        mockMvc = MockMvcBuilders.standaloneSetup(new AiToolsInternalController(
                        deptService, staffService, scheduleService, registrationService))
                .setControllerAdvice(new AiExceptionHandler())
                .build();
    }

    @Test
    void listsDeptsWithReadScope() throws Exception {
        Dept dept = new Dept();
        dept.setId(1L);
        dept.setDeptName("内科");
        when(deptService.list(null)).thenReturn(List.of(dept));

        mockMvc.perform(get("/api/internal/ai-tools/depts")
                        .requestAttr(DelegatedJwtInterceptor.CLAIMS_ATTR, readClaims()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$[0].id").value(1));
    }

    @Test
    void rejectsDeptQueryWithoutScope() throws Exception {
        mockMvc.perform(get("/api/internal/ai-tools/depts")
                        .requestAttr(DelegatedJwtInterceptor.CLAIMS_ATTR, writeOnlyClaims()))
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.code").value("INSUFFICIENT_SCOPE"));
    }

    @Test
    void createsRegistrationWithDelegatedClaims() throws Exception {
        when(registrationService.register(any(AiToolRegistrationCreateDTO.class), eq(writeClaims())))
                .thenReturn(88L);

        mockMvc.perform(post("/api/internal/ai-tools/registrations")
                        .requestAttr(DelegatedJwtInterceptor.CLAIMS_ATTR, writeClaims())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"patientId\":999,\"scheduleId\":20,\"idempotencyKey\":\"idem-1\",\"interruptId\":\"i-1\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.id").value(88));

        verify(registrationService).register(any(AiToolRegistrationCreateDTO.class), eq(writeClaims()));
    }

    @Test
    void mapsToolErrorsToStablePayload() throws Exception {
        when(registrationService.register(any(), any()))
                .thenThrow(new AiToolException("SLOT_SOLD_OUT", "号源已满"));

        mockMvc.perform(post("/api/internal/ai-tools/registrations")
                        .requestAttr(DelegatedJwtInterceptor.CLAIMS_ATTR, writeClaims())
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"patientId\":10,\"scheduleId\":20,\"idempotencyKey\":\"idem-1\",\"interruptId\":\"i-1\"}"))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.code").value("SLOT_SOLD_OUT"));
    }

    private static AiDelegationClaims readClaims() {
        return new AiDelegationClaims(1L, 10L, "c-1",
                List.of("dept:read", "doctor:read", "schedule:read"), null, "jti-1");
    }

    private static AiDelegationClaims writeClaims() {
        return new AiDelegationClaims(1L, 10L, "c-1",
                List.of("registration:create"), "i-1", "jti-2");
    }

    private static AiDelegationClaims writeOnlyClaims() {
        return writeClaims();
    }
}
