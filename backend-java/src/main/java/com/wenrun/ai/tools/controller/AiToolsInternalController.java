package com.wenrun.ai.tools.controller;

import com.wenrun.ai.delegation.AiDelegationClaims;
import com.wenrun.ai.tools.dto.AiToolRegistrationCreateDTO;
import com.wenrun.ai.tools.interceptor.DelegatedJwtInterceptor;
import com.wenrun.ai.tools.service.AiToolsRegistrationService;
import com.wenrun.entity.Dept;
import com.wenrun.service.DeptService;
import com.wenrun.service.ScheduleService;
import com.wenrun.service.StaffService;
import com.wenrun.vo.ScheduleVO;
import com.wenrun.vo.StaffVO;
import jakarta.servlet.http.HttpServletRequest;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.time.LocalDate;
import java.util.List;
import java.util.Map;

@RestController
@RequiredArgsConstructor
@RequestMapping("/api/internal/ai-tools")
public class AiToolsInternalController {

    private final DeptService deptService;
    private final StaffService staffService;
    private final ScheduleService scheduleService;
    private final AiToolsRegistrationService registrationService;

    @GetMapping("/depts")
    public List<Dept> depts(
            @RequestParam(required = false) Integer status,
            HttpServletRequest request
    ) {
        AiToolsRegistrationService.requireScope(claims(request), "dept:read");
        return deptService.list(status);
    }

    @GetMapping("/staff")
    public List<StaffVO> staff(
            @RequestParam(required = false) Long deptId,
            @RequestParam(required = false) Integer status,
            HttpServletRequest request
    ) {
        AiToolsRegistrationService.requireScope(claims(request), "doctor:read");
        return staffService.list(deptId, status);
    }

    @GetMapping("/schedules")
    public List<ScheduleVO> schedules(
            @RequestParam(required = false) Long deptId,
            @RequestParam(required = false) LocalDate workDate,
            @RequestParam(required = false) Long staffId,
            HttpServletRequest request
    ) {
        AiToolsRegistrationService.requireScope(claims(request), "schedule:read");
        return scheduleService.list(deptId, workDate, staffId);
    }

    @PostMapping("/registrations")
    public Map<String, Long> createRegistration(
            @RequestBody AiToolRegistrationCreateDTO dto,
            HttpServletRequest request
    ) {
        Long id = registrationService.register(dto, claims(request));
        return Map.of("id", id);
    }

    private static AiDelegationClaims claims(HttpServletRequest request) {
        return DelegatedJwtInterceptor.claimsFrom(request);
    }
}
