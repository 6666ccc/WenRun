package com.wenrun.repository;

import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.time.LocalDateTime;

/**
 * Token 黑名单 Mapper —— 登出时记录已失效 Token 的 JTI。
 */
@Mapper
public interface TokenBlacklistRepository {

    int insert(@Param("jti") String jti, @Param("expiresAt") LocalDateTime expiresAt);

    int existsByJti(@Param("jti") String jti);

    int deleteExpired(@Param("now") LocalDateTime now);
}
