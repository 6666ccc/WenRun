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

    interface Handle extends AutoCloseable {
        @Override
        void close();
    }
}
