package com.wenrun.controller;

import com.wenrun.common.Result;
import com.wenrun.dto.PrescriptionCreateDTO;
import com.wenrun.service.PrescriptionService;
import com.wenrun.vo.PrescriptionVO;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * 处方接口 — 开方、查询与作废
 */
@RestController
@RequestMapping("/api/prescriptions")
@RequiredArgsConstructor
public class PrescriptionController {

    private final PrescriptionService prescriptionService;

    /** GET /api/prescriptions — 查询某次就诊的处方列表 */
    @GetMapping
    public Result<List<PrescriptionVO>> listByVisit(@RequestParam Long visitId) {
        return Result.success(prescriptionService.listByVisit(visitId));
    }

    /** GET /api/prescriptions/pending-dispense — 查询待发药处方列表 */
    @GetMapping("/pending-dispense")
    public Result<List<PrescriptionVO>> pendingDispense() {
        return Result.success(prescriptionService.listPendingDispense());
    }

    /** GET /api/prescriptions/{id} — 查询处方详情 */
    @GetMapping("/{id}")
    public Result<PrescriptionVO> get(@PathVariable Long id) {
        return Result.success(prescriptionService.getById(id));
    }

    /** POST /api/prescriptions — 开具处方 */
    @PostMapping
    public Result<Long> create(@Valid @RequestBody PrescriptionCreateDTO dto) {
        return Result.success(prescriptionService.create(dto));
    }

    /** POST /api/prescriptions/{id}/cancel — 作废待缴费处方 */
    @PostMapping("/{id}/cancel")
    public Result<Void> cancel(@PathVariable Long id) {
        prescriptionService.cancel(id);
        return Result.success();
    }
}
