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
import com.wenrun.repository.PatientRepository;
import com.wenrun.repository.AiConversationRepository;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.springframework.core.task.AsyncTaskExecutor;

import java.util.Optional;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class AiControllerConcurrencyTest {

    private final aiService aiGateway = mock(aiService.class);
    private final PatientRepository patientRepository = mock(PatientRepository.class);
    private final ChatMessageRepository messageRepository = mock(ChatMessageRepository.class);
    private final ConversationOwnershipService ownershipService = mock(ConversationOwnershipService.class);
    private final DelegationTokenService tokenService = mock(DelegationTokenService.class);
    private final ConversationExecutionLock lock = mock(ConversationExecutionLock.class);
    private final AsyncTaskExecutor executor = mock(AsyncTaskExecutor.class);
    private final AiPatientMemoryService memoryService = mock(AiPatientMemoryService.class);
    private final AiConversationRepository conversationRepository = mock(AiConversationRepository.class);
    private final aiController controller = new aiController(
            aiGateway, patientRepository, messageRepository, ownershipService,
            executor, tokenService, lock, memoryService, conversationRepository);

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
