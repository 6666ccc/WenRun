package com.wenrun.ai.security;

import java.util.Set;

/** Java 内部 Tool API 从委托 JWT 解析出的可信调用身份。 */
public record DelegatedToolPrincipal(
        Long userId,
        Long patientId,
        String accountType,
        Set<String> scopes,
        String tokenId) {

    public boolean hasScope(String scope) {
        return scopes != null && scopes.contains(scope);
    }
}
