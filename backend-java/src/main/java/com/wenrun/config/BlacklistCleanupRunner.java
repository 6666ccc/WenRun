package com.wenrun.config;

import com.wenrun.repository.TokenBlacklistRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.dao.DataAccessException;
import org.springframework.stereotype.Component;

import java.time.LocalDateTime;

/**
 * 启动时清理已过期的 Token 黑名单记录。
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class BlacklistCleanupRunner implements ApplicationRunner {

    private final TokenBlacklistRepository blacklistMapper;

    @Override
    public void run(ApplicationArguments args) {
        try {
            int removed = blacklistMapper.deleteExpired(LocalDateTime.now());
            if (removed > 0) log.info("已清理 {} 条过期 token 黑名单记录", removed);
        } catch (DataAccessException ex) {
            log.warn("token 黑名单表未就绪，跳过启动清理。请在 MySQL 执行 docs/SQL/migration_token_blacklist.sql：{}", ex.getMessage());
        }
    }
}
