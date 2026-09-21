package com.wenrun.controller;

import com.wenrun.common.Result;
import com.wenrun.service.RegistrationService;
import com.wenrun.vo.RegistrationVO;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/**
 * 患者维度的挂号查询。登录身份来自 JWT，patientId 必须通过授权校验。
 */
@RestController
@RequestMapping("/api/patients/{patientId}/registrations")
@RequiredArgsConstructor
public class PatientRegistrationController {

    private final RegistrationService registrationService;

    @GetMapping
    public Result<List<RegistrationVO>> list(@PathVariable Long patientId,
                                             @RequestParam(required = false) Integer status) {
        return Result.success(registrationService.list(patientId, null, null, status));
    }
}
