package com.wenrun.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

/**
 * API Key 配置 —— 用于服务间调用认证（如 Python AI 服务 → Java 后端）。
 *
 * <p>相比于 OAuth2 client_credentials 模式，API Key 方案更轻量：
 * <ul>
 *   <li>不需要请求 /oauth2/token 获取令牌</li>
 *   <li>不需要管理令牌过期和刷新</li>
 *   <li>直接在 HTTP 请求头中传递预共享密钥</li>
 * </ul>
 *
 * <p>生产环境建议通过环境变量 WENRUN_API_KEY 注入，不要将密钥提交到代码仓库。
 */
@Data
@Component
@ConfigurationProperties(prefix = "wenrun")
public class ApiKeyProperties {

    /** 服务间调用的预共享 API Key */
    private String apiKey;
}
