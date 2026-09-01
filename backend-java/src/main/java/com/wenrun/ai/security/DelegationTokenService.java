package com.wenrun.ai.security;

import com.wenrun.common.ResultCode;
import com.wenrun.common.exception.BusinessException;

import java.util.Collection;
import java.util.Date;
import java.util.LinkedHashSet;
import java.util.Set;
import java.util.UUID;

import javax.crypto.SecretKey;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import java.time.Duration;
import java.time.Instant;

import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.Claims;
import io.jsonwebtoken.JwtException;
import io.jsonwebtoken.io.Decoders;
import io.jsonwebtoken.security.Keys;
@Service
public class DelegationTokenService {

    private static final int MIN_SECRET_BYTES = 32;
    private final SecretKey secretKey;
    private final Duration ttl;

    public DelegationTokenService(
            @Value("${AI_DELEGATION_SIGNING_SECRET:}") String signingSecret,
            @Value("${AI_DELEGATION_TTL:5m}") Duration tokenTtl) {
        this.secretKey = createSigningKey(signingSecret);
        this.ttl = validateTtl(tokenTtl);
    }

    private SecretKey createSigningKey(String signingSecret) {
        if (!StringUtils.hasText(signingSecret)) {
            throw new IllegalStateException(
                    "AI_DELEGATION_SIGNING_SECRET 未配置");
        }

        try {
            byte[] keyBytes = Decoders.BASE64.decode(signingSecret);

            if (keyBytes.length < MIN_SECRET_BYTES) {
                throw new IllegalStateException(
                        "AI_DELEGATION_SIGNING_SECRET 至少需要 32 字节");
            }

            return Keys.hmacShaKeyFor(keyBytes);
        } catch (IllegalArgumentException ex) {
            throw new IllegalStateException("AI_DELEGATION_SIGNING_SECRET 不是有效的 Base64",ex);
        }
    }

    private Duration validateTtl(Duration tokenTtl) {
        if (tokenTtl == null || tokenTtl.isZero() || tokenTtl.isNegative()) {
            throw new IllegalStateException(
                    "AI_DELEGATION_TTL 必须大于 0");
        }
        return tokenTtl;
    }

    public String issue(Long userId, String accountType, Long patientId, Set<String> scopes) {
        Instant now = Instant.now();

        return Jwts.builder()
                .issuer("wenrun-java")
                .subject(String.valueOf(userId))
                .claim("accountType", accountType)
                .claim("patientId", patientId)
                .claim("scopes", scopes)
                .issuedAt(Date.from(now))
                .expiration(Date.from(now.plus(ttl)))
                .id(UUID.randomUUID().toString())
                .signWith(secretKey)
                .compact();
    }

    /**
     * 校验由本服务签发、且仅供 Python 代理调用内部 Tool API 的令牌。
     * Python 不能自行选择用户、患者或权限；这些身份信息只能来自该令牌。
     */
    public DelegatedToolPrincipal verifyForToolApi(String token) {
        if (!StringUtils.hasText(token)) {
            throw new BusinessException(ResultCode.UNAUTHORIZED, "缺少 AI 委托令牌");
        }
        try {
            Claims claims = Jwts.parser()
                    .verifyWith(secretKey)
                    .requireIssuer("wenrun-java")
                    .build()
                    .parseSignedClaims(token)
                    .getPayload();

            Long userId = parseUserId(claims.getSubject());
            Long patientId = parseOptionalLong(claims.get("patientId"));
            Set<String> scopes = parseScopes(claims.get("scopes"));
            return new DelegatedToolPrincipal(userId, patientId,
                    claims.get("accountType", String.class), scopes, claims.getId());
        } catch (JwtException | IllegalArgumentException ex) {
            throw new BusinessException(ResultCode.UNAUTHORIZED, "AI 委托令牌无效或已过期");
        }
    }

    private Long parseUserId(String subject) {
        try {
            return Long.valueOf(subject);
        } catch (NumberFormatException ex) {
            throw new IllegalArgumentException("invalid delegated subject", ex);
        }
    }

    private Long parseOptionalLong(Object value) {
        if (value == null) {
            return null;
        }
        if (value instanceof Number number) {
            return number.longValue();
        }
        return Long.valueOf(String.valueOf(value));
    }

    private Set<String> parseScopes(Object value) {
        if (!(value instanceof Collection<?> collection)) {
            return Set.of();
        }
        Set<String> scopes = new LinkedHashSet<>();
        for (Object item : collection) {
            if (item instanceof String scope && StringUtils.hasText(scope)) {
                scopes.add(scope);
            }
        }
        return Set.copyOf(scopes);
    }
}
