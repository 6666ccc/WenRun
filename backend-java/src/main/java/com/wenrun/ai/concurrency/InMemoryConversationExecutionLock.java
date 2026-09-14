package com.wenrun.ai.concurrency;

import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;

import java.util.Optional;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentMap;

/** Single-process implementation used only when the configured auth/session store is memory. */
@Component
@ConditionalOnProperty(name = "wenrun.auth.session-store", havingValue = "memory", matchIfMissing = true)
public class InMemoryConversationExecutionLock implements ConversationExecutionLock {

    private final ConcurrentMap<String, String> owners = new ConcurrentHashMap<>();

    @Override
    public Optional<Handle> tryAcquire(Long userId, String conversationId) {
        String key = userId + ":" + conversationId;
        String ownerToken = UUID.randomUUID().toString();
        if (owners.putIfAbsent(key, ownerToken) != null) {
            return Optional.empty();
        }
        return Optional.of(() -> owners.remove(key, ownerToken));
    }
}
