package com.wenrun.ai.controller;

import com.wenrun.ai.security.DelegationTokenService;
import com.wenrun.ai.service.ConversationOwnershipService;
import com.wenrun.ai.service.aiService;
import com.wenrun.ai.vo.aiRequest;
import com.wenrun.common.Result;
import com.wenrun.common.context.UserContext;
import com.wenrun.config.RequestTrace;
import com.wenrun.entity.ChatMessage;
import com.wenrun.entity.Patient;
import com.wenrun.repository.ChatMessageRepository;
import com.wenrun.repository.PatientRepository;
import jakarta.validation.Valid;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.http.MediaType;
import org.springframework.core.task.AsyncTaskExecutor;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.util.StringUtils;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.io.IOException;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.Future;
import java.util.concurrent.atomic.AtomicReference;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.function.Consumer;

@Slf4j
@RestController
@RequestMapping("/api/ai")
public class aiController {

    private static final long STREAM_TIMEOUT_MILLIS = 300_000L;

    private final aiService aiService;
    private final PatientRepository patientRepository;
    private final ChatMessageRepository chatMessageRepository;
    private final ConversationOwnershipService ownershipService;
    private final AsyncTaskExecutor streamExecutor;
    private final DelegationTokenService delegationTokenService;

    public aiController(
            aiService aiService,
            PatientRepository patientRepository,
            ChatMessageRepository chatMessageRepository,
            ConversationOwnershipService ownershipService,
            @Qualifier("aiStreamExecutor") AsyncTaskExecutor streamExecutor,
            DelegationTokenService delegationTokenService) {
        this.aiService = aiService;
        this.patientRepository = patientRepository;
        this.chatMessageRepository = chatMessageRepository;
        this.ownershipService = ownershipService;
        this.streamExecutor = streamExecutor;
        this.delegationTokenService = delegationTokenService;
    }

    @PostMapping(value = "/chat/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public SseEmitter chatStream(@Valid @RequestBody aiRequest request) {
        prepare(request);
        ChatMessage existingUser = chatMessageRepository.selectByClientRequestId(
                request.getConversationId(), request.getUserId(), request.getClientRequestId(), "user");
        if (existingUser != null) {
            if (!Objects.equals(existingUser.getContent(), request.getMessage())) {
                return rejectedRequestStream(request, "AI_REQUEST_ID_REUSED", "请求 ID 已对应其他消息，请重新发送");
            }
            ChatMessage existingAssistant = chatMessageRepository.selectByClientRequestId(
                    request.getConversationId(), request.getUserId(), request.getClientRequestId(), "assistant");
            return duplicateRequestStream(request, existingAssistant);
        }
        if (!saveMessage(request.getConversationId(), request.getUserId(), request.getClientRequestId(), "user",
                request.getMessage())) {
            ChatMessage racedUser = chatMessageRepository.selectByClientRequestId(
                    request.getConversationId(), request.getUserId(), request.getClientRequestId(), "user");
            if (racedUser != null) {
                ChatMessage racedAssistant = chatMessageRepository.selectByClientRequestId(
                        request.getConversationId(), request.getUserId(), request.getClientRequestId(), "assistant");
                return duplicateRequestStream(request, racedAssistant);
            }
            throw new IllegalStateException("AI 用户消息保存失败");
        }
        return stream(
                consumer -> aiService.streamChat(request, consumer),
                request.getConversationId(),
                request.getUserId(),
                request.getClientRequestId());
    }

    @DeleteMapping("/conversations/{conversationId}")
    public Result<Void> deleteConversation(@PathVariable String conversationId) {
        Long userId = UserContext.getUserId();
        ownershipService.assertOwned(conversationId, userId);
        chatMessageRepository.deleteByConversationId(conversationId);
        return Result.success();
    }

    private void prepare(aiRequest request) {
        if (!StringUtils.hasText(request.getConversationId())) {
            request.setConversationId("java-" + UUID.randomUUID());
        } else {
            request.setConversationId(request.getConversationId().trim());
        }
        if (!StringUtils.hasText(request.getClientRequestId())) {
            request.setClientRequestId("client-" + UUID.randomUUID());
        } else {
            request.setClientRequestId(request.getClientRequestId().trim());
        }
        Long userId = UserContext.getUserId();
        ownershipService.establishIfAbsent(request.getConversationId(), userId);
        request.setUserId(userId);
        request.setPatientId(currentPatientId(userId));
        request.setRequestId(RequestTrace.get());
        request.setDelegatedToken(
                delegationTokenService.issue(
                        request.getUserId(),
                        UserContext.getAccountType(),
                        request.getPatientId(),
                        Set.of(
                                "departments:read",
                                "schedules:read",
                                "staff:read",
                                "registrations:read")));
    }

    private SseEmitter stream(StreamAction action, String conversationId, Long userId,
            String clientRequestId) {
        SseEmitter emitter = new SseEmitter(STREAM_TIMEOUT_MILLIS);
        AtomicBoolean terminal = new AtomicBoolean(false);
        AtomicReference<Future<?>> upstreamTask = new AtomicReference<>();
        Runnable cancelUpstream = () -> {
            terminal.set(true);
            Future<?> task = upstreamTask.get();
            if (task != null) {
                task.cancel(true);
            }
        };
        emitter.onTimeout(cancelUpstream);
        emitter.onError(error -> cancelUpstream.run());
        emitter.onCompletion(cancelUpstream);

        Future<?> task = streamExecutor.submit(() -> {
            StringBuilder accumulatedReply = new StringBuilder();
            try {
                action.run(event -> {
                    if (event == null || terminal.get()) {
                        return;
                    }
                    String type = String.valueOf(event.get("type"));
                    if ("token".equals(type) && event.get("content") != null) {
                        accumulatedReply.append(event.get("content"));
                    }
                    send(emitter, event);
                    if ("done".equals(type)) {
                        String reply = event.get("reply") instanceof String value && StringUtils.hasText(value)
                                ? value
                                : accumulatedReply.toString();
                        saveMessage(conversationId, userId, clientRequestId, "assistant", reply);
                        terminal.set(true);
                        emitter.complete();
                    } else if ("error".equals(type)) {
                        terminal.set(true);
                        emitter.complete();
                    }
                });
                if (terminal.compareAndSet(false, true)) {
                    sendError(emitter, "AI_STREAM_INCOMPLETE", "AI 流式响应意外结束");
                    emitter.complete();
                }
            } catch (Exception ex) {
                log.warn("AI 流式聊天失败: {}", ex.getMessage());
                if (terminal.compareAndSet(false, true)) {
                    sendError(emitter, "AI_STREAM_FAILED",
                            ex.getMessage() == null ? "AI 流式聊天失败" : ex.getMessage());
                    emitter.complete();
                }
            }
        });
        upstreamTask.set(task);
        if (terminal.get()) {
            task.cancel(true);
        }
        return emitter;
    }

    private void sendError(SseEmitter emitter, String code, String message) {
        Map<String, Object> error = new LinkedHashMap<>();
        error.put("type", "error");
        error.put("code", code);
        error.put("message", message);
        try {
            emitter.send(SseEmitter.event().data(error));
        } catch (IOException ignored) {
            // 客户端可能已经断开。
        }
    }

    private void send(SseEmitter emitter, Map<String, Object> event) {
        try {
            emitter.send(SseEmitter.event().data(event));
        } catch (IOException ex) {
            throw new IllegalStateException("SSE 推送失败", ex);
        }
    }

    private SseEmitter duplicateRequestStream(aiRequest request, ChatMessage existingAssistant) {
        return requestResultStream(request, existingAssistant == null ? "AI_REQUEST_IN_PROGRESS" : null,
                existingAssistant == null ? "该消息正在处理中，请勿重复发送" : null, existingAssistant);
    }

    private SseEmitter rejectedRequestStream(aiRequest request, String code, String message) {
        return requestResultStream(request, code, message, null);
    }

    private SseEmitter requestResultStream(aiRequest request, String errorCode, String errorMessage,
            ChatMessage existingAssistant) {
        SseEmitter emitter = new SseEmitter(10_000L);
        streamExecutor.submit(() -> {
            try {
                if (errorCode == null && existingAssistant != null) {
                    Map<String, Object> done = new LinkedHashMap<>();
                    done.put("type", "done");
                    done.put("reply", existingAssistant.getContent());
                    done.put("conversationId", request.getConversationId());
                    send(emitter, done);
                } else {
                    sendError(emitter, errorCode, errorMessage);
                }
                emitter.complete();
            } catch (Exception ex) {
                emitter.completeWithError(ex);
            }
        });
        return emitter;
    }

    private boolean saveMessage(String conversationId, Long userId, String clientRequestId,
            String role, String content) {
        if (!StringUtils.hasText(conversationId) || userId == null || !StringUtils.hasText(content)) {
            return false;
        }
        try {
            ChatMessage message = new ChatMessage();
            message.setConversationId(conversationId);
            message.setUserId(userId);
            message.setClientRequestId(clientRequestId);
            message.setRole(role);
            message.setContent(content);
            return chatMessageRepository.insert(message) > 0;
        } catch (DuplicateKeyException ex) {
            return false;
        } catch (Exception ex) {
            log.warn("保存 AI 对话消息失败: {}", ex.getMessage());
            return false;
        }
    }

    private Long currentPatientId(Long userId) {
        if (userId == null) {
            return null;
        }
        Patient patient = patientRepository.selectByUserId(userId);
        return patient == null ? null : patient.getId();
    }

    @FunctionalInterface
    private interface StreamAction {
        void run(Consumer<Map<String, Object>> consumer);
    }
}
