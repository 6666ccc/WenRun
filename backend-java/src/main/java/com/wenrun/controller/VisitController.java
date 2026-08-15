package com.wenrun.controller;

import com.wenrun.common.Result;
import com.wenrun.dto.VisitUpdateDTO;
import com.wenrun.service.VisitService;
import com.wenrun.service.support.CurrentStaffSupport;
import com.wenrun.vo.VisitVO;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * 门诊就诊接口 — 接诊、病历填写与完诊
 */
@RestController
@RequestMapping("/api/visits")
@RequiredArgsConstructor
public class VisitController {

    private final VisitService visitService;
    private final CurrentStaffSupport currentStaffSupport;

    /** GET /api/visits — 查询就诊记录列表（医生端自动按当前登录医生过滤） */
    @GetMapping
    public Result<List<VisitVO>> list(@RequestParam(required = false) Integer status,
                                      @RequestParam(required = false) Long staffId) {
        Long effectiveStaffId = currentStaffSupport.resolveStaffId(staffId);
        return Result.success(visitService.list(status, effectiveStaffId));
    }

    /** GET /api/visits/{id} — 查询就诊详情 */
    @GetMapping("/{id}")
    public Result<VisitVO> get(@PathVariable Long id) {
        return Result.success(visitService.getById(id));
    }

    /** POST /api/visits/start/{registrationId} — 根据挂号单开始接诊 */
    @PostMapping("/start/{registrationId}")
    public Result<Long> start(@PathVariable Long registrationId) {
        return Result.success(visitService.startVisit(registrationId));
    }

    /** PUT /api/visits/{id} — 更新主诉、诊断或标记完诊 */
    @PutMapping("/{id}")
    public Result<Void> update(@PathVariable Long id, @RequestBody VisitUpdateDTO dto) {
        visitService.updateVisit(id, dto);
        return Result.success();
    }
}
