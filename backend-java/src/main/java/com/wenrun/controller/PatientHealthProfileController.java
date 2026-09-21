package com.wenrun.controller;

import com.wenrun.common.Result;
import com.wenrun.dto.HealthProfileDTO;
import com.wenrun.service.PatientHealthProfileService;
import com.wenrun.vo.HealthProfileVO;
import com.wenrun.vo.HealthSnapshotVO;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/**
 * 患者健康档案
 */
@RestController
@RequestMapping("/api/patients/{patientId}/health-profile")
@RequiredArgsConstructor
public class PatientHealthProfileController {

    private final PatientHealthProfileService healthProfileService;

    /** GET /api/patients/{patientId}/health-profile — 查询当前健康档案 */
    @GetMapping
    public Result<HealthProfileVO> get(@PathVariable Long patientId) {
        return Result.success(healthProfileService.get(patientId));
    }

    /** POST /api/patients/{patientId}/health-profile — 新建健康档案并写入快照 */
    @PostMapping
    public Result<HealthProfileVO> create(@PathVariable Long patientId,
                                          @RequestBody HealthProfileDTO dto) {
        return Result.success(healthProfileService.create(patientId, dto));
    }

    /** PUT /api/patients/{patientId}/health-profile — 更新当前值并追加快照 */
    @PutMapping
    public Result<HealthProfileVO> update(@PathVariable Long patientId,
                                          @RequestBody HealthProfileDTO dto) {
        return Result.success(healthProfileService.update(patientId, dto));
    }

    /** DELETE /api/patients/{patientId}/health-profile — 删除当前健康档案 */
    @DeleteMapping
    public Result<Void> delete(@PathVariable Long patientId) {
        healthProfileService.delete(patientId);
        return Result.success();
    }

    /** GET /api/patients/{patientId}/health-profile/snapshots — 查询历史快照 */
    @GetMapping("/snapshots")
    public Result<List<HealthSnapshotVO>> listSnapshots(@PathVariable Long patientId) {
        return Result.success(healthProfileService.listSnapshots(patientId));
    }

    /** DELETE /api/patients/{patientId}/health-profile/snapshots/{snapshotId} — 删除一条快照 */
    @DeleteMapping("/snapshots/{snapshotId}")
    public Result<Void> deleteSnapshot(@PathVariable Long patientId,
                                       @PathVariable Long snapshotId) {
        healthProfileService.deleteSnapshot(patientId, snapshotId);
        return Result.success();
    }
}
