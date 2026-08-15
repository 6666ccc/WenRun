package com.wenrun.util;

import com.wenrun.common.ResultCode;
import com.wenrun.common.exception.BusinessException;
import com.nimbusds.jose.JOSEException;
import com.nimbusds.jose.JWSAlgorithm;
import com.nimbusds.jose.JWSHeader;
import com.nimbusds.jose.crypto.MACSigner;
import com.nimbusds.jose.crypto.MACVerifier;
import com.nimbusds.jwt.JWTClaimsSet;
import com.nimbusds.jwt.SignedJWT;
import org.springframework.util.StringUtils;

import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;
import java.text.ParseException;
import java.time.Instant;
import java.time.LocalDateTime;
import java.time.ZoneId;
import java.util.*;

public final class JwtUtil {

    /** HS256 算法标识 */
    private static final JWSAlgorithm ALGORITHM = JWSAlgorithm.HS256;

    private JwtUtil() {
    }

    // ==================== 签发 ====================

    /**
     * 签发用户 JWT Token。
     *
     * @param userId        用户 ID
     * @param username      用户名
     * @param accountType   账户类型（staff / patient）
     * @param portalType    门户类型（front / admin）
     * @param roles         角色列表
     * @param staffId       员工 ID（可为 null）
     * @param patientId     患者 ID（可为 null）
     * @param secret        HS256 签名密钥
     * @param expirySeconds Token 有效秒数
     * @return JWT 字符串
     */
    public static String createToken(Long userId, String username, String accountType,
            String portalType, List<String> roles,
            Long staffId, Long patientId,
            String secret, int expirySeconds) {
        try {
            Instant now = Instant.now();
            JWTClaimsSet.Builder builder = new JWTClaimsSet.Builder()
                    .subject(String.valueOf(userId))
                    .jwtID(UUID.randomUUID().toString().replace("-", ""))
                    .issueTime(Date.from(now))
                    .expirationTime(Date.from(now.plusSeconds(expirySeconds)))
                    .claim("username", username)
                    .claim("account_type", accountType)
                    .claim("portal_type", portalType)
                    .claim("roles", roles != null ? roles : Collections.emptyList());

            if (staffId != null) {
                builder.claim("staff_id", staffId);
            }
            if (patientId != null) {
                builder.claim("patient_id", patientId);
            }

            SignedJWT jwt = new SignedJWT(
                    new JWSHeader(ALGORITHM),
                    builder.build());
            jwt.sign(new MACSigner(new SecretKeySpec(
                    secret.getBytes(StandardCharsets.UTF_8), "HmacSHA256")));

            return jwt.serialize();
        } catch (JOSEException e) {
            throw new IllegalStateException("JWT 签发失败", e);
        }
    }

    // ==================== 验证 & 解析 ====================

    /**
     * 验证 JWT 签名、过期时间，返回解析后的 Claims。
     *
     * @param token  JWT 字符串
     * @param secret 签名密钥
     * @return JWT Claims Set
     * @throws BusinessException Token 无效或过期
     */
    public static JWTClaimsSet verifyAndParse(String token, String secret) {
        if (!StringUtils.hasText(token)) {
            throw new BusinessException(ResultCode.UNAUTHORIZED, "未登录或 Token 无效");
        }
        try {
            SignedJWT jwt = SignedJWT.parse(token);

            // 签名验证
            if (!jwt.verify(new MACVerifier(new SecretKeySpec(
                    secret.getBytes(StandardCharsets.UTF_8), "HmacSHA256")))) {
                throw new BusinessException(ResultCode.UNAUTHORIZED, "Token 签名无效");
            }

            JWTClaimsSet claims = jwt.getJWTClaimsSet();

            // 过期校验
            Date exp = claims.getExpirationTime();
            if (exp == null || exp.before(new Date())) {
                throw new BusinessException(ResultCode.UNAUTHORIZED, "登录已过期，请重新登录");
            }

            return claims;
        } catch (ParseException e) {
            throw new BusinessException(ResultCode.UNAUTHORIZED, "Token 格式无效");
        } catch (JOSEException e) {
            throw new BusinessException(ResultCode.UNAUTHORIZED, "Token 验证失败");
        }
    }

    /**
     * 从 JWT 中安全提取 Claims 而不做签名验证。
     * 仅用于提取 JTI / 过期时间做黑名单操作。
     */
    public static JWTClaimsSet parseWithoutVerify(String token) {
        try {
            return SignedJWT.parse(token).getJWTClaimsSet();
        } catch (ParseException e) {
            return null;
        }
    }

    // ==================== Claims 提取（验证后使用） ====================

    public static Long getUserId(JWTClaimsSet claims) {
        String sub = claims.getSubject();
        return sub != null ? Long.parseLong(sub) : null;
    }

    public static String getJti(JWTClaimsSet claims) {
        return claims.getJWTID();
    }

    public static String getStringClaim(JWTClaimsSet claims, String key) {
        Object val = claims.getClaim(key);
        return val != null ? String.valueOf(val) : null;
    }

    @SuppressWarnings("unchecked")
    public static List<String> getStringListClaim(JWTClaimsSet claims, String key) {
        Object val = claims.getClaim(key);
        if (val instanceof List<?> list) {
            return list.stream().map(String::valueOf).toList();
        }
        return Collections.emptyList();
    }

    public static Long getLongClaim(JWTClaimsSet claims, String key) {
        Object val = claims.getClaim(key);
        if (val == null)
            return null;
        if (val instanceof Number n)
            return n.longValue();
        return Long.parseLong(String.valueOf(val));
    }

    /**
     * 获取 Token 过期时间的 LocalDateTime 表示。
     */
    public static LocalDateTime getExpiresAtLocal(JWTClaimsSet claims) {
        Date exp = claims.getExpirationTime();
        if (exp == null)
            return null;
        return LocalDateTime.ofInstant(exp.toInstant(), ZoneId.systemDefault());
    }
}
