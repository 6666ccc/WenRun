package com.wenrun.controller;

import com.wenrun.common.Result;
import com.wenrun.dto.PatientQueryDTO;
import com.wenrun.entity.Patient;
import com.wenrun.service.PatientService;
import com.wenrun.vo.PatientVO;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/**
 * 患者接口
 */
@RestController
@RequestMapping("/api/patients")
@RequiredArgsConstructor
public class PatientController {

    private final PatientService patientService;

    /** GET /api/patients — 按条件查询患者列表 */
    @GetMapping
    public Result<List<PatientVO>> list(PatientQueryDTO query) {
        return Result.success(patientService.list(query));
    }

    /** GET /api/patients/{id} — 查询患者详情 */
    @GetMapping("/{id}")
    public Result<PatientVO> getById(@PathVariable Long id) {
        return Result.success(patientService.getById(id));
    }

    /** POST /api/patients — 新建患者档案 */
    @PostMapping
    public Result<Long> create(@RequestBody Patient patient) {
        return Result.success(patientService.create(patient));
    }

    /** PUT /api/patients/{id} — 更新患者档案 */
    @PutMapping("/{id}")
    public Result<Void> update(@PathVariable Long id, @RequestBody Patient patient) {
        patient.setId(id);
        patientService.update(patient);
        return Result.success();
    }
}
