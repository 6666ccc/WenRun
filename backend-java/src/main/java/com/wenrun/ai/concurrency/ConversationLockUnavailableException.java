package com.wenrun.ai.concurrency;

/** The distributed lock backend failed; callers must not continue without serialization. */
public class ConversationLockUnavailableException extends RuntimeException {
    public ConversationLockUnavailableException(String message, Throwable cause) {
        super(message, cause);
    }
}
