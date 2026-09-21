package com.wenrun.controller;

import com.wenrun.common.Result;
import com.wenrun.common.context.UserContext;
import com.wenrun.service.PatientAccessService;
import com.wenrun.vo.AccessiblePatientVO;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/**
 * 当前登录账号可管理的患者列表。
 */
@RestController
@RequestMapping("/api/me")
@RequiredArgsConstructor
public class MeController {

    private final PatientAccessService patientAccess;

    @GetMapping("/patients")
    public Result<List<AccessiblePatientVO>> listMyPatients() {
        return Result.success(patientAccess.listAccessible(UserContext.getUserId()));
    }
}
