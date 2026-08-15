package com.wenrun.controller;

import com.wenrun.common.Result;
import com.wenrun.service.DashboardService;
import com.wenrun.vo.DashboardVO;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * 工作台接口 — 今日运营数据汇总
 */
@RestController
@RequestMapping("/api/dashboard")
@RequiredArgsConstructor
public class DashboardController {

    private final DashboardService dashboardService;

    /** GET /api/dashboard — 获取今日挂号、就诊、收费等统计 */
    @GetMapping
    public Result<DashboardVO> summary() {
        return Result.success(dashboardService.summary());
    }
}
