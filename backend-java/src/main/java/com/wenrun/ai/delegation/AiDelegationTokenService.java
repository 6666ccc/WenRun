package com.wenrun.ai.delegation;

import com.nimbusds.jose.JOSEException;
import com.nimbusds.jose.JWSAlgorithm;
import com.nimbusds.jose.JWSHeader;
import com.nimbusds.jose.crypto.MACSigner;
import com.nimbusds.jose.crypto.MACVerifier;
import com.nimbusds.jwt.JWTClaimsSet;
import com.nimbusds.jwt.SignedJWT;
import lombok.RequiredArgsConstructor;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;
import java.text.ParseException;
import java.time.Instant;
import java.util.Date;
import java.util.List;
import java.util.UUID;

@Service
@RequiredArgsConstructor
@EnableConfigurationProperties(AiDelegationProperties.class)
public class AiDelegationTokenService {

    public static final String AUDIENCE = "ai-tools";
    public static final List<String> READ_SCOPES = List.of(
            "dept:read",
            "doctor:read",
            "schedule:read"
    );
    public static final String SCOPE_REGISTRATION_CREATE = "registration:create";

    private final AiDelegationProperties properties;

    public String issueReadToken(Long userId, Long patientId, String conversationId) {
        return sign(userId, patientId, conversationId, READ_SCOPES, null);
    }

    public String issueWriteToken(Long userId, Long patientId, String conversationId, String interruptId) {
        return sign(
                userId,
                patientId,
                conversationId,
                List.of("dept:read", "doctor:read", "schedule:read", SCOPE_REGISTRATION_CREATE),
                interruptId
        );
    }

    public AiDelegationClaims verify(String token, String requiredScope) {
        if (!StringUtils.hasText(token)) {
            throw new AiDelegationException("missing delegation token");
        }
        try {
            SignedJWT jwt = SignedJWT.parse(token);
            byte[] secret = properties.getSecret().getBytes(StandardCharsets.UTF_8);
            if (!jwt.verify(new MACVerifier(new SecretKeySpec(secret, "HmacSHA256")))) {
                throw new AiDelegationException("invalid delegation token signature");
            }
            JWTClaimsSet claims = jwt.getJWTClaimsSet();
            Date exp = claims.getExpirationTime();
            if (exp == null || exp.before(new Date())) {
                throw new AiDelegationException("delegation token expired");
            }
            List<String> audience = claims.getAudience();
            if (audience == null || !audience.contains(AUDIENCE)) {
                throw new AiDelegationException("invalid delegation token audience");
            }
            List<String> scopes = readScopes(claims);
            if (requiredScope != null && !scopes.contains(requiredScope)) {
                throw new AiDelegationException("insufficient delegation scope");
            }
            String interruptId = stringClaim(claims, "interrupt_id");
            if (SCOPE_REGISTRATION_CREATE.equals(requiredScope) && !StringUtils.hasText(interruptId)) {
                throw new AiDelegationException("write token must bind interruptId");
            }
            return new AiDelegationClaims(
                    Long.parseLong(claims.getSubject()),
                    longClaim(claims, "patient_id"),
                    stringClaim(claims, "conversation_id"),
                    scopes,
                    interruptId,
                    claims.getJWTID()
            );
        } catch (ParseException | JOSEException | NumberFormatException ex) {
            throw new AiDelegationException("invalid delegation token");
        }
    }

    public AiDelegationClaims verify(String token) {
        return verify(token, null);
    }

    private String sign(
            Long userId,
            Long patientId,
            String conversationId,
            List<String> scopes,
            String interruptId
    ) {
        try {
            Instant now = Instant.now();
            JWTClaimsSet.Builder builder = new JWTClaimsSet.Builder()
                    .subject(userId.toString())
                    .audience(AUDIENCE)
                    .claim("patient_id", patientId)
                    .claim("conversation_id", conversationId)
                    .claim("scope", scopes)
                    .jwtID(UUID.randomUUID().toString())
                    .issueTime(Date.from(now))
                    .expirationTime(Date.from(now.plusSeconds(properties.getExpirySeconds())));
            if (StringUtils.hasText(interruptId)) {
                builder.claim("interrupt_id", interruptId);
            }
            SignedJWT jwt = new SignedJWT(new JWSHeader(JWSAlgorithm.HS256), builder.build());
            jwt.sign(new MACSigner(new SecretKeySpec(
                    properties.getSecret().getBytes(StandardCharsets.UTF_8),
                    "HmacSHA256"
            )));
            return jwt.serialize();
        } catch (JOSEException ex) {
            throw new IllegalStateException("failed to issue delegation token", ex);
        }
    }

    @SuppressWarnings("unchecked")
    private static List<String> readScopes(JWTClaimsSet claims) {
        Object value = claims.getClaim("scope");
        if (value instanceof List<?> list) {
            return list.stream().map(String::valueOf).toList();
        }
        if (value instanceof String text && StringUtils.hasText(text)) {
            return List.of(text.split(" "));
        }
        return List.of();
    }

    private static String stringClaim(JWTClaimsSet claims, String name) {
        Object value = claims.getClaim(name);
        return value == null ? null : String.valueOf(value);
    }

    private static Long longClaim(JWTClaimsSet claims, String name) {
        Object value = claims.getClaim(name);
        if (value == null) {
            return null;
        }
        if (value instanceof Number number) {
            return number.longValue();
        }
        return Long.parseLong(String.valueOf(value));
    }
}
