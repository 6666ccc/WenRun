package com.wenrun.controller;

import com.wenrun.common.Result;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

/**
 * 健康检查，用于验证服务是否启动
 */
@RestController
@RequestMapping("/api/health")
public class HealthController {

    /** GET /api/health — 返回服务运行状态 */
    @GetMapping
    public Result<Map<String, String>> health() {
        return Result.success(Map.of("status", "UP", "app", "WenRun"));
    }
}
