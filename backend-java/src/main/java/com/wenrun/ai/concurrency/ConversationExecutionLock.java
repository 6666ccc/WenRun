package com.wenrun.ai.concurrency;

import java.util.Optional;

/**
 * Serializes stateful AI execution for one user's conversation.
 *
 * <p>The user id is part of the key deliberately: browser supplied conversation ids are not
 * globally unique and must never create cross-tenant contention.</p>
 */
public interface ConversationExecutionLock {

    Optional<Handle> tryAcquire(Long userId, String conversationId);
    default boolean ownsExecution(Long userId, String conversationId, String executionId) { return false; }

    interface Handle extends AutoCloseable {
        default String executionId() { return null; }
        default boolean isValid() { return true; }
        @Override
        void close();
    }
}
