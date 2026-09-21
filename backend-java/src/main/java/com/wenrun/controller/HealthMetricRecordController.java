package com.wenrun.controller;

import com.wenrun.common.Result;
import com.wenrun.dto.HealthMetricRecordDTO;
import com.wenrun.service.HealthMetricRecordService;
import com.wenrun.vo.HealthMetricRecordVO;
import com.wenrun.vo.HealthMetricTrendVO;
import com.wenrun.vo.HealthMetricTypeVO;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/**
 * 患者健康指标纵向记录与趋势，按 patientId 归属。
 */
@RestController
@RequiredArgsConstructor
public class HealthMetricRecordController {

    private final HealthMetricRecordService healthMetricRecordService;

    /** GET /api/health-metrics/types — 趋势图可切换的指标（含 BMI），不属于某个患者 */
    @GetMapping("/api/health-metrics/types")
    public Result<List<HealthMetricTypeVO>> listTypes() {
        return Result.success(healthMetricRecordService.listTypes());
    }

    /** GET /api/patients/{patientId}/health-metrics/trend?metricType=WEIGHT&range=30 */
    @GetMapping("/api/patients/{patientId}/health-metrics/trend")
    public Result<HealthMetricTrendVO> trend(@PathVariable Long patientId,
                                             @RequestParam String metricType,
                                             @RequestParam(required = false) Integer range) {
        return Result.success(healthMetricRecordService.trend(patientId, metricType, range));
    }

    /** GET /api/patients/{patientId}/health-metrics — 最近记录，可按指标过滤 */
    @GetMapping("/api/patients/{patientId}/health-metrics")
    public Result<List<HealthMetricRecordVO>> list(@PathVariable Long patientId,
                                                   @RequestParam(required = false) String metricType,
                                                   @RequestParam(required = false) Integer limit) {
        return Result.success(healthMetricRecordService.list(patientId, metricType, limit));
    }

    /** GET /api/patients/{patientId}/health-metrics/{id} */
    @GetMapping("/api/patients/{patientId}/health-metrics/{id}")
    public Result<HealthMetricRecordVO> get(@PathVariable Long patientId, @PathVariable Long id) {
        return Result.success(healthMetricRecordService.get(patientId, id));
    }

    /** POST /api/patients/{patientId}/health-metrics */
    @PostMapping("/api/patients/{patientId}/health-metrics")
    public Result<HealthMetricRecordVO> create(@PathVariable Long patientId,
                                               @RequestBody HealthMetricRecordDTO dto) {
        return Result.success(healthMetricRecordService.create(patientId, dto));
    }

    /** PUT /api/patients/{patientId}/health-metrics/{id} */
    @PutMapping("/api/patients/{patientId}/health-metrics/{id}")
    public Result<HealthMetricRecordVO> update(@PathVariable Long patientId,
                                               @PathVariable Long id,
                                               @RequestBody HealthMetricRecordDTO dto) {
        return Result.success(healthMetricRecordService.update(patientId, id, dto));
    }

    /** DELETE /api/patients/{patientId}/health-metrics/{id} */
    @DeleteMapping("/api/patients/{patientId}/health-metrics/{id}")
    public Result<Void> delete(@PathVariable Long patientId, @PathVariable Long id) {
        healthMetricRecordService.delete(patientId, id);
        return Result.success();
    }
}
