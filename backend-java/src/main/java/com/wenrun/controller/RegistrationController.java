package com.wenrun.controller;

import com.wenrun.common.Result;
import com.wenrun.common.constant.BizStatus;
import com.wenrun.dto.RegistrationCreateDTO;
import com.wenrun.dto.RegistrationRescheduleDTO;
import com.wenrun.service.RegistrationService;
import com.wenrun.service.support.CurrentStaffSupport;
import com.wenrun.vo.RegistrationVO;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * 挂号接口 — 预约、退号与待就诊查询
 */
@RestController
@RequestMapping("/api/registrations")
@RequiredArgsConstructor
public class RegistrationController {

    private final RegistrationService registrationService;
    private final CurrentStaffSupport currentStaffSupport;

    /** GET /api/registrations — 查询挂号列表（医生端自动按当前登录医生过滤） */
    @GetMapping
    public Result<List<RegistrationVO>> list(@RequestParam(required = false) Long patientId,
            @RequestParam(required = false) Long userId,
            @RequestParam(required = false) Long registrantUserId,
            @RequestParam(required = false) Long staffId,
            @RequestParam(required = false) Integer status) {
        Long effectiveStaffId = currentStaffSupport.resolveStaffId(staffId);
        return Result.success(registrationService.list(
                patientId, userId, registrantUserId, effectiveStaffId, status));
    }

    /** GET /api/registrations/pending — 查询待就诊挂号（医生端自动过滤） */
    @GetMapping("/pending")
    public Result<List<RegistrationVO>> pending(@RequestParam(required = false) Long staffId) {
        Long effectiveStaffId = currentStaffSupport.resolveStaffId(staffId);
        return Result.success(registrationService.list(
                null, null, null, effectiveStaffId, BizStatus.REG_REGISTERED));
    }

    /** POST /api/registrations — 患者挂号 */
    @PostMapping
    public Result<Long> register(@Valid @RequestBody RegistrationCreateDTO dto) {
        return Result.success(registrationService.register(dto));
    }

    /** PUT /api/registrations/{id}/schedule — 将有效挂号改到另一个号源 */
    @PutMapping("/{id}/schedule")
    public Result<Void> reschedule(@PathVariable Long id,
                                   @Valid @RequestBody RegistrationRescheduleDTO dto) {
        registrationService.reschedule(id, dto.getScheduleId());
        return Result.success();
    }

    /** POST /api/registrations/{id}/cancel — 退号 */
    @PostMapping("/{id}/cancel")
    public Result<Void> cancel(@PathVariable Long id) {
        registrationService.cancel(id);
        return Result.success();
    }
}
