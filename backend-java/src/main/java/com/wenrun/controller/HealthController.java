package com.wenrun.controller;

import com.wenrun.common.Result;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.data.redis.connection.RedisConnectionFactory;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;
import javax.sql.DataSource;

/**
 * 健康检查，用于验证服务是否启动
 */
@RestController
@RequestMapping("/api/health")
@RequiredArgsConstructor
public class HealthController {
    private final DataSource dataSource;
    private final ObjectProvider<RedisConnectionFactory> redisConnectionFactories;

    /** GET /api/health — 返回服务运行状态 */
    @GetMapping
    public Result<Map<String, String>> health() {
        return Result.success(Map.of("status", "UP", "app", "WenRun"));
    }

    /** Internal readiness: dependencies must respond, not just the HTTP process. */
    @GetMapping("/ready")
    public ResponseEntity<Map<String, String>> ready() {
        var redisConnectionFactory = redisConnectionFactories.getIfAvailable();
        if (redisConnectionFactory == null)
            return ResponseEntity.status(503).body(Map.of("status", "unavailable"));
        try (var connection = dataSource.getConnection();
             var statement = connection.createStatement();
             var redis = redisConnectionFactory.getConnection()) {
            statement.setQueryTimeout(3);
            try (var result = statement.executeQuery("SELECT 1")) {
                if (!result.next() || !"PONG".equals(redis.ping()))
                    return ResponseEntity.status(503).body(Map.of("status", "unavailable"));
            }
            return ResponseEntity.ok(Map.of("status", "ready"));
        } catch (Exception ignored) {
            return ResponseEntity.status(503).body(Map.of("status", "unavailable"));
        }
    }
}
