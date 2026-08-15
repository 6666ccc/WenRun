package com.wenrun.controller;

import com.wenrun.common.Result;
import com.wenrun.entity.Schedule;
import com.wenrun.service.ScheduleService;
import com.wenrun.vo.ScheduleVO;
import lombok.RequiredArgsConstructor;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDate;
import java.util.List;

/**
 * 排班接口
 */
@RestController
@RequestMapping("/api/schedules")
@RequiredArgsConstructor
public class ScheduleController {

    private final ScheduleService scheduleService;

    /** GET /api/schedules — 按科室、日期、医生查询排班 */
    @GetMapping
    public Result<List<ScheduleVO>> list(@RequestParam(required = false) Long deptId,
                                         @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate workDate,
                                         @RequestParam(required = false) Long staffId) {
        return Result.success(scheduleService.list(deptId, workDate, staffId));
    }

    /** GET /api/schedules/{id} — 查询排班详情（含科室、医生名称） */
    @GetMapping("/{id}")
    public Result<ScheduleVO> get(@PathVariable Long id) {
        return Result.success(scheduleService.getDetail(id));
    }

    /** POST /api/schedules — 新建排班 */
    @PostMapping
    public Result<Long> create(@RequestBody Schedule schedule) {
        return Result.success(scheduleService.create(schedule));
    }

    /** PUT /api/schedules/{id} — 更新排班 */
    @PutMapping("/{id}")
    public Result<Void> update(@PathVariable Long id, @RequestBody Schedule schedule) {
        schedule.setId(id);
        scheduleService.update(schedule);
        return Result.success();
    }
}
