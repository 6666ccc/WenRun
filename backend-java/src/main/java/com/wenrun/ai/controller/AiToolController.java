package com.wenrun.ai.controller;

import com.wenrun.ai.security.DelegatedToolContext;
import com.wenrun.ai.security.DelegatedToolPrincipal;
import com.wenrun.ai.vo.AiRegistrationCreateRequest;
import com.wenrun.ai.vo.AiMemoryWriteRequest;
import com.wenrun.ai.service.AiPatientMemoryService;
import com.wenrun.common.Result;
import com.wenrun.common.ResultCode;
import com.wenrun.common.constant.AccountType;
import com.wenrun.common.constant.BizStatus;
import com.wenrun.common.exception.BusinessException;
import com.wenrun.dto.RegistrationCreateDTO;
import com.wenrun.entity.Dept;
import com.wenrun.entity.AiPatientMemory;
import com.wenrun.entity.ChatMessage;
import com.wenrun.repository.ChatMessageRepository;
import com.wenrun.entity.Staff;
import com.wenrun.service.DeptService;
import com.wenrun.service.RegistrationService;
import com.wenrun.service.ScheduleService;
import com.wenrun.service.StaffService;
import com.wenrun.vo.RegistrationVO;
import com.wenrun.vo.ScheduleVO;
import com.wenrun.vo.StaffVO;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.time.LocalDate;
import java.util.List;

/**
 * 只供 Python AI 编排服务调用的只读业务能力。
 * 对 Agent 提供科室、专家、号源与本人挂号的兼容查询模型；这些内部接口不等同于患者端功能入口。
 * 写操作只开放挂号与退号两项，且仅限患者账号本人；不提供通用 SQL。
 * 患者维度的数据只按委托令牌里的 patientId 过滤，Python 不能自选患者。
 */
@RestController
@RequestMapping("/api/internal/ai-tools")
@RequiredArgsConstructor
public class AiToolController {

    private final DeptService deptService;
    private final ScheduleService scheduleService;
    private final StaffService staffService;
    private final RegistrationService registrationService;
    private final AiPatientMemoryService memoryService;
    private final ChatMessageRepository chatMessageRepository;

    @GetMapping("/departments")
    public Result<List<Dept>> listDepartments(@RequestParam(required = false) Integer status) {
        requireScope("departments:read");
        return Result.success(deptService.list(status));
    }

    @GetMapping("/departments/{id}")
    public Result<Dept> getDepartment(@PathVariable Long id) {
        requireScope("departments:read");
        return Result.success(deptService.getById(id));
    }

    @GetMapping("/schedules")
    public Result<List<ScheduleVO>> listSchedules(
            @RequestParam(required = false) Long deptId,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate workDate,
            @RequestParam(required = false) Long staffId) {
        requireScope("schedules:read");
        return Result.success(scheduleService.list(deptId, workDate, staffId));
    }

    @GetMapping("/schedules/{id}")
    public Result<ScheduleVO> getSchedule(@PathVariable Long id) {
        requireScope("schedules:read");
        return Result.success(scheduleService.getDetail(id));
    }

    @GetMapping("/staff")
    public Result<List<StaffVO>> listStaff(
            @RequestParam(required = false) Long deptId,
            @RequestParam(required = false) Integer status) {
        requireScope("staff:read");
        return Result.success(staffService.list(deptId, status));
    }

    @GetMapping("/staff/{id}")
    public Result<Staff> getStaff(@PathVariable Long id) {
        requireScope("staff:read");
        return Result.success(staffService.getById(id));
    }

    /** 只返回令牌所属患者本人的挂号记录，不接受调用方指定 patientId。 */
    @GetMapping("/registrations")
    public Result<List<RegistrationVO>> listMyRegistrations(@RequestParam(required = false) Integer status) {
        return Result.success(registrationService.list(
                requirePatientId(), null, null, status));
    }

    /** 对齐 {@code /api/registrations/pending}，只看本人待就诊的号。 */
    @GetMapping("/registrations/pending")
    public Result<List<RegistrationVO>> listMyPendingRegistrations() {
        return Result.success(registrationService.list(
                requirePatientId(), null, null, BizStatus.REG_REGISTERED));
    }

    /** 为令牌所属患者挂号。真正的过期、号源、重复校验与幂等都在 RegistrationServiceImpl 里。 */
    @PostMapping("/registrations")
    public Result<Long> createMyRegistration(@Valid @RequestBody AiRegistrationCreateRequest body) {
        Long patientId = requireWritablePatientId();
        RegistrationCreateDTO dto = new RegistrationCreateDTO();
        dto.setPatientId(patientId);
        dto.setScheduleId(body.getScheduleId());
        dto.setIdempotencyKey(body.getIdempotencyKey());
        return Result.success(registrationService.register(dto));
    }

    /** 退号。挂号单归属由 RegistrationServiceImpl 依据桥接进来的 UserContext 校验。 */
    @PostMapping("/registrations/{id}/cancel")
    public Result<Void> cancelMyRegistration(@PathVariable Long id) {
        requireWritablePatientId();
        registrationService.cancel(id);
        return Result.success();
    }

    @GetMapping("/memories")
    public Result<List<AiPatientMemory>> listMyMemories() {
        requireScope("memories:read");
        return Result.success(memoryService.listActive(requireMemoryPatientId(false), 20));
    }

    /** Python 只能在 LangGraph interrupt 已获患者确认后调用此接口。 */
    @PostMapping("/memories")
    public Result<AiPatientMemory> createMyMemory(@Valid @RequestBody AiMemoryWriteRequest body) {
        Long patientId = requireMemoryPatientId(true);
        DelegatedToolPrincipal principal = DelegatedToolContext.getRequired();
        // Provenance is resolved from the delegated user scope. Never trust a
        // model-supplied database message id, even if one is present in JSON.
        body.setSourceMessageId(null);
        if (body.getSourceConversationId() != null) {
            List<ChatMessage> recent = chatMessageRepository.selectRecentByConversationIdAndUserId(
                    body.getSourceConversationId(), principal.userId(), 10);
            for (int index = recent.size() - 1; index >= 0; index--) {
                ChatMessage message = recent.get(index);
                if ("user".equals(message.getRole())) {
                    body.setSourceMessageId(message.getId());
                    break;
                }
            }
        }
        return Result.success(memoryService.createConfirmed(patientId, body));
    }

    @DeleteMapping("/memories/{memoryId}")
    public Result<Void> deleteMyMemory(@PathVariable String memoryId) {
        memoryService.delete(requireMemoryPatientId(true), memoryId);
        return Result.success();
    }

    private void requireScope(String scope) {
        if (!DelegatedToolContext.getRequired().hasScope(scope)) {
            throw new BusinessException(ResultCode.FORBIDDEN, "AI 委托令牌没有所需权限");
        }
    }

    private Long requirePatientId() {
        DelegatedToolPrincipal principal = DelegatedToolContext.getRequired();
        if (!principal.hasScope("registrations:read")) {
            throw new BusinessException(ResultCode.FORBIDDEN, "AI 委托令牌没有所需权限");
        }
        if (principal.patientId() == null) {
            throw new BusinessException(ResultCode.FORBIDDEN, "当前账号还没有绑定患者档案");
        }
        return principal.patientId();
    }

    /**
     * 写操作的准入：必须有写 scope、必须是患者账号、必须绑定了患者档案。
     * 只有患者本人能通过助手办理，内部账号与医生账号一律走原有的柜台流程。
     */
    private Long requireWritablePatientId() {
        DelegatedToolPrincipal principal = DelegatedToolContext.getRequired();
        if (!principal.hasScope("registrations:write")) {
            throw new BusinessException(ResultCode.FORBIDDEN, "AI 委托令牌没有所需权限");
        }
        if (!AccountType.PATIENT.equals(principal.accountType())) {
            throw new BusinessException(ResultCode.FORBIDDEN, "只有患者本人可以通过助手办理挂号");
        }
        if (principal.patientId() == null) {
            throw new BusinessException(ResultCode.FORBIDDEN, "当前账号还没有绑定患者档案");
        }
        return principal.patientId();
    }

    private Long requireMemoryPatientId(boolean write) {
        DelegatedToolPrincipal principal = DelegatedToolContext.getRequired();
        String scope = write ? "memories:write" : "memories:read";
        if (!principal.hasScope(scope)) {
            throw new BusinessException(ResultCode.FORBIDDEN, "AI 委托令牌没有所需权限");
        }
        if (write && !AccountType.PATIENT.equals(principal.accountType())) {
            throw new BusinessException(ResultCode.FORBIDDEN, "只有患者本人可以管理长期记忆");
        }
        if (principal.patientId() == null) {
            throw new BusinessException(ResultCode.FORBIDDEN, "当前账号还没有绑定患者档案");
        }
        return principal.patientId();
    }
}
