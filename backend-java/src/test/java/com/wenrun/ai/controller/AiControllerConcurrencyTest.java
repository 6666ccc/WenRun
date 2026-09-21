package com.wenrun.ai.controller;

import com.wenrun.ai.concurrency.ConversationExecutionLock;
import com.wenrun.ai.security.DelegationTokenService;
import com.wenrun.ai.service.ConversationOwnershipService;
import com.wenrun.ai.service.AiPatientMemoryService;
import com.wenrun.ai.service.aiService;
import com.wenrun.ai.vo.aiRequest;
import com.wenrun.common.context.UserContext;
import com.wenrun.entity.ChatMessage;
import com.wenrun.repository.ChatMessageRepository;
import com.wenrun.repository.AiConversationRepository;
import com.wenrun.service.PatientAccessService;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.core.task.AsyncTaskExecutor;

import java.util.Map;
import java.util.Optional;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.function.Consumer;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.nullable;
import static org.mockito.Mockito.atLeastOnce;
import static org.mockito.Mockito.doAnswer;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class AiControllerConcurrencyTest {

    private final aiService aiGateway = mock(aiService.class);
    private final PatientAccessService patientAccess = mock(PatientAccessService.class);
    private final ChatMessageRepository messageRepository = mock(ChatMessageRepository.class);
    private final ConversationOwnershipService ownershipService = mock(ConversationOwnershipService.class);
    private final DelegationTokenService tokenService = mock(DelegationTokenService.class);
    private final ConversationExecutionLock lock = mock(ConversationExecutionLock.class);
    private final AsyncTaskExecutor executor = mock(AsyncTaskExecutor.class);
    private final AiPatientMemoryService memoryService = mock(AiPatientMemoryService.class);
    private final AiConversationRepository conversationRepository = mock(AiConversationRepository.class);
    private final aiController controller = new aiController(
            aiGateway, patientAccess, messageRepository, ownershipService,
            executor, tokenService, lock, memoryService, conversationRepository);

    @BeforeEach
    void stubPatientAccess() {
        when(patientAccess.resolvePatientId(nullable(Long.class))).thenReturn(11L);
    }

    @AfterEach
    void clearUserContext() {
        UserContext.clear();
    }

    @Test
    void busyConversationDoesNotPersistOrCallPython() {
        UserContext.setUserId(7L);
        when(tokenService.issue(any(), any(), any(), any())).thenReturn("delegated");
        when(lock.tryAcquire(7L, "conversation-1")).thenReturn(Optional.empty());
        aiRequest request = request("conversation-1", "request-1");

        controller.chatStream(request);

        verify(messageRepository, never()).insert(any());
        verify(aiGateway, never()).streamChat(any(), any());
    }

    @Test
    void completedIdempotentReplayBypassesConversationLock() {
        UserContext.setUserId(7L);
        when(tokenService.issue(any(), any(), any(), any())).thenReturn("delegated");
        ChatMessage user = message("user", "你好");
        ChatMessage assistant = message("assistant", "您好");
        when(messageRepository.selectByClientRequestId(
                "conversation-1", 7L, "request-1", "user")).thenReturn(user);
        when(messageRepository.selectByClientRequestId(
                "conversation-1", 7L, "request-1", "assistant")).thenReturn(assistant);

        controller.chatStream(request("conversation-1", "request-1"));

        verify(lock, never()).tryAcquire(any(), anyString());
        verify(messageRepository, never()).insert(any());
        verify(aiGateway, never()).streamChat(any(), any());
    }

    @Test
    void completedStreamDoesNotInterruptLockRelease() throws Exception {
        UserContext.setUserId(7L);
        ConversationExecutionLock.Handle handle = mock(ConversationExecutionLock.Handle.class);
        AtomicBoolean closedWhileInterrupted = new AtomicBoolean();
        CountDownLatch started = new CountDownLatch(1);
        CountDownLatch allowDone = new CountDownLatch(1);
        CountDownLatch closed = new CountDownLatch(1);
        doAnswer(invocation -> {
            closedWhileInterrupted.set(Thread.currentThread().isInterrupted());
            closed.countDown();
            return null;
        }).when(handle).close();
        when(tokenService.issue(any(), any(), any(), any())).thenReturn("delegated");
        when(lock.tryAcquire(7L, "conversation-1")).thenReturn(Optional.of(handle));
        when(messageRepository.insert(any())).thenReturn(1);
        doAnswer(invocation -> {
            started.countDown();
            assertThat(allowDone.await(2, TimeUnit.SECONDS)).isTrue();
            @SuppressWarnings("unchecked")
            Consumer<Map<String, Object>> consumer = invocation.getArgument(1);
            consumer.accept(Map.of("type", "done", "reply", "办完了"));
            return null;
        }).when(aiGateway).streamChat(any(), any());
        ExecutorService pool = Executors.newSingleThreadExecutor();
        try {
            aiController asyncController = new aiController(
                    aiGateway, patientAccess, messageRepository, ownershipService,
                    asyncExecutor(pool), tokenService, lock, memoryService, conversationRepository);

            asyncController.chatStream(request("conversation-1", "request-1"));
            assertThat(started.await(2, TimeUnit.SECONDS)).isTrue();
            allowDone.countDown();
            assertThat(closed.await(2, TimeUnit.SECONDS)).isTrue();
        } finally {
            pool.shutdownNow();
        }

        verify(handle, atLeastOnce()).close();
        assertThat(closedWhileInterrupted.get()).isFalse();
    }

    private static AsyncTaskExecutor asyncExecutor(ExecutorService pool) {
        return new AsyncTaskExecutor() {
            @Override
            public void execute(Runnable task) {
                pool.execute(task);
            }

            @Override
            public Future<?> submit(Runnable task) {
                return pool.submit(task);
            }
        };
    }

    private aiRequest request(String conversationId, String requestId) {
        aiRequest request = new aiRequest();
        request.setMessage("你好");
        request.setConversationId(conversationId);
        request.setClientRequestId(requestId);
        return request;
    }

    private ChatMessage message(String role, String content) {
        ChatMessage message = new ChatMessage();
        message.setRole(role);
        message.setContent(content);
        return message;
    }
}
