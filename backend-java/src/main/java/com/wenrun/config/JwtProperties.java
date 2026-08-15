package com.wenrun.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

/**
 * JWT 配置属性。
 *
 * <h3>配置示例（application.yml）</h3>
 * <pre>{@code
 * jwt:
 *   secret: your-256-bit-secret   # HS256 密钥，至少 32 字符
 *   expiry: 604800                # Token 过期时间（秒），默认 7 天
 * }</pre>
 */
@Data
@Component
@ConfigurationProperties(prefix = "jwt")
public class JwtProperties {

    /** HS256 签名密钥，长度至少 32 字符 */
    private String secret;

    /** Access Token 过期时间（秒），默认 604800（7 天） */
    private int expiry = 604800;
}
