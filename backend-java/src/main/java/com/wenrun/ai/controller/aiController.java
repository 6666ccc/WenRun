package com.wenrun.ai.controller;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.wenrun.ai.concurrency.ConversationExecutionLock;
import com.wenrun.ai.concurrency.ConversationLockUnavailableException;
import com.wenrun.ai.security.DelegationTokenService;
import com.wenrun.ai.service.ConversationOwnershipService;
import com.wenrun.ai.service.AiPatientMemoryService;
import com.wenrun.ai.service.aiService;
import com.wenrun.ai.vo.aiRequest;
import com.wenrun.ai.vo.aiResumeRequest;
import com.wenrun.ai.vo.AiConversationVO;
import com.wenrun.ai.vo.AiChatMessageVO;
import com.wenrun.common.Result;
import com.wenrun.common.ResultCode;
import com.wenrun.common.context.UserContext;
import com.wenrun.common.exception.BusinessException;
import com.wenrun.config.RequestTrace;
import com.wenrun.entity.AiConversation;
import com.wenrun.entity.ChatMessage;
import com.wenrun.repository.ChatMessageRepository;
import com.wenrun.service.PatientAccessService;
import jakarta.validation.Valid;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.http.MediaType;
import org.springframework.core.task.AsyncTaskExecutor;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.util.StringUtils;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.io.IOException;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
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
    private static final int RECOVERY_MESSAGE_LIMIT = 24;
    private static final ObjectMapper JSON = new ObjectMapper();

    private final aiService aiService;
    private final PatientAccessService patientAccess;
    private final ChatMessageRepository chatMessageRepository;
    private final ConversationOwnershipService ownershipService;
    private final AsyncTaskExecutor streamExecutor;
    private final DelegationTokenService delegationTokenService;
    private final ConversationExecutionLock conversationExecutionLock;
    private final AiPatientMemoryService memoryService;
    private final com.wenrun.repository.AiConversationRepository conversationRepository;

    public aiController(
            aiService aiService,
            PatientAccessService patientAccess,
            ChatMessageRepository chatMessageRepository,
            ConversationOwnershipService ownershipService,
            @Qualifier("aiStreamExecutor") AsyncTaskExecutor streamExecutor,
            DelegationTokenService delegationTokenService,
            ConversationExecutionLock conversationExecutionLock,
            AiPatientMemoryService memoryService,
            com.wenrun.repository.AiConversationRepository conversationRepository) {
        this.aiService = aiService;
        this.patientAccess = patientAccess;
        this.chatMessageRepository = chatMessageRepository;
        this.ownershipService = ownershipService;
        this.streamExecutor = streamExecutor;
        this.delegationTokenService = delegationTokenService;
        this.conversationExecutionLock = conversationExecutionLock;
        this.memoryService = memoryService;
        this.conversationRepository = conversationRepository;
    }

    @GetMapping("/conversations")
    public Result<List<AiConversationVO>> listConversations(
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "30") int size) {
        Long userId = UserContext.getUserId();
        int boundedSize = Math.max(1, Math.min(size, 50));
        int offset = Math.max(0, page) * boundedSize;
        return Result.success(conversationRepository.selectSummariesByUserId(
                userId, offset, boundedSize));
    }

    @GetMapping("/conversations/{conversationId}/messages")
    public Result<List<AiChatMessageVO>> listMessages(
            @PathVariable String conversationId,
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "100") int size) {
        Long userId = UserContext.getUserId();
        ownershipService.assertOwned(conversationId, userId);
        int boundedSize = Math.max(1, Math.min(size, 100));
        int offset = Math.max(0, page) * boundedSize;
        return Result.success(chatMessageRepository.selectPageByConversationIdAndUserId(
                        conversationId, userId, offset, boundedSize)
                .stream().map(AiChatMessageVO::from).toList());
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
        ConversationExecutionLock.Handle lock;
        try {
            lock = acquireConversationLock(request.getUserId(), request.getConversationId());
        } catch (ConversationLockUnavailableException ex) {
            return rejectedRequestStream(request, "AI_CONVERSATION_LOCK_UNAVAILABLE", "会话服务暂不可用，请稍后再试");
        }
        if (lock == null) {
            return rejectedRequestStream(request, "AI_CONVERSATION_BUSY", "该会话正在处理上一条消息，请稍后再试");
        }
        try {
            if (!Boolean.FALSE.equals(request.getMemoryEnabled())) {
                request.setRecoveryMessages(chatMessageRepository.selectRecentByConversationIdAndUserId(
                        request.getConversationId(), request.getUserId(), RECOVERY_MESSAGE_LIMIT));
                if (request.getPatientId() != null) {
                    request.setLongTermMemories(memoryService.listActive(request.getPatientId(), 20));
                }
            }
            if (!saveMessage(request.getConversationId(), request.getUserId(), request.getClientRequestId(), "user",
                    request.getMessage())) {
                ChatMessage racedUser = chatMessageRepository.selectByClientRequestId(
                        request.getConversationId(), request.getUserId(), request.getClientRequestId(), "user");
                if (racedUser != null) {
                    lock.close();
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
                    request.getClientRequestId(),
                    lock,
                    null);
        } catch (RuntimeException ex) {
            lock.close();
            throw ex;
        }
    }

    @PostMapping(value = "/chat/resume", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public SseEmitter chatResume(@Valid @RequestBody aiResumeRequest request) {
        prepareResume(request);
        ConversationExecutionLock.Handle lock;
        try {
            lock = acquireConversationLock(request.getUserId(), request.getConversationId());
        } catch (ConversationLockUnavailableException ex) {
            return immediateErrorStream("AI_CONVERSATION_LOCK_UNAVAILABLE", "会话服务暂不可用，请稍后再试");
        }
        if (lock == null) {
            return immediateErrorStream("AI_CONVERSATION_BUSY", "该会话正在处理上一条消息，请稍后再试");
        }
        return stream(
                consumer -> aiService.streamResume(request, consumer),
                request.getConversationId(),
                request.getUserId(),
                request.getClientRequestId(),
                lock,
                request.getInterruptId() == null ? "" : request.getInterruptId());
    }

    @DeleteMapping("/conversations/{conversationId}")
    public Result<Void> deleteConversation(@PathVariable String conversationId) {
        Long userId = UserContext.getUserId();
        ConversationExecutionLock.Handle lock;
        try {
            lock = acquireConversationLock(userId, conversationId);
        } catch (ConversationLockUnavailableException ex) {
            throw new BusinessException(ResultCode.SERVICE_UNAVAILABLE, "会话服务暂不可用，请稍后再试");
        }
        if (lock == null) {
            throw new BusinessException(409, "该会话正在处理消息，请稍后再删除");
        }
        try {
            ownershipService.delete(conversationId, userId);
            aiService.deleteConversationMemory(conversationId, userId);
            return Result.success();
        } finally {
            lock.close();
        }
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
        request.setUserId(userId);
        request.setPatientId(resolveConversationPatient(
                request.getConversationId(), userId, request.getPatientId()));
        ownershipService.establishIfAbsent(
                request.getConversationId(), userId, request.getPatientId());
        request.setRequestId(RequestTrace.get());
        request.setDelegatedToken(
                delegationTokenService.issue(
                        request.getUserId(),
                        UserContext.getAccountType(),
                        request.getPatientId(),
                        DelegationTokenService.PATIENT_ASSISTANT_SCOPES));
    }

    /**
     * 恢复只能发生在已存在且属于当前用户的会话上，所以用 assertOwned 而不是 establishIfAbsent。
     * 委托令牌必须重新签发：原令牌 5 分钟就过期，而患者盯着确认卡片可能想很久。
     */
    private void prepareResume(aiResumeRequest request) {
        request.setConversationId(request.getConversationId().trim());
        if (!StringUtils.hasText(request.getClientRequestId())) {
            request.setClientRequestId("client-" + UUID.randomUUID());
        } else {
            request.setClientRequestId(request.getClientRequestId().trim());
        }
        Long userId = UserContext.getUserId();
        ownershipService.assertOwned(request.getConversationId(), userId);
        request.setUserId(userId);
        request.setPatientId(resolveConversationPatient(
                request.getConversationId(), userId, request.getPatientId()));
        request.setRequestId(RequestTrace.get());
        request.setDelegatedToken(
                delegationTokenService.issue(
                        userId,
                        UserContext.getAccountType(),
                        request.getPatientId(),
                        DelegationTokenService.PATIENT_ASSISTANT_SCOPES));
    }

    private SseEmitter stream(StreamAction action, String conversationId, Long userId,
            String clientRequestId, ConversationExecutionLock.Handle lock,
            String resumeInterruptId) {
        SseEmitter emitter = new SseEmitter(STREAM_TIMEOUT_MILLIS);
        AtomicBoolean terminal = new AtomicBoolean(false);
        AtomicBoolean abort = new AtomicBoolean(false);
        AtomicReference<Future<?>> upstreamTask = new AtomicReference<>();
        Runnable abortUpstream = () -> {
            terminal.set(true);
            abort.set(true);
            Future<?> task = upstreamTask.get();
            if (task != null) {
                task.cancel(true);
            }
        };
        emitter.onTimeout(abortUpstream);
        emitter.onError(error -> abortUpstream.run());
        // complete() 会在工作线程上同步触发 onCompletion。这里不能 cancel(true)，
        // 否则 finally 里释放 Redis 会话锁会被 Lettuce 当成 Command interrupted。
        emitter.onCompletion(() -> terminal.set(true));

        Future<?> task;
        try {
            task = streamExecutor.submit(() -> {
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
                        log.info("ai_stream_event type=done conversationId={} clientRequestId={}",
                                conversationId, clientRequestId);
                        String reply = event.get("reply") instanceof String value && StringUtils.hasText(value)
                                ? value
                                : accumulatedReply.toString();
                        if (resumeInterruptId != null) {
                            chatMessageRepository.completeLatestConfirmation(
                                    conversationId, userId, resumeInterruptId);
                        }
                        saveMessage(conversationId, userId, clientRequestId, "assistant", reply);
                        terminal.set(true);
                        emitter.complete();
                    } else if ("confirm".equals(type)) {
                        // 写操作挂起等患者确认，本轮到此为止：Python 不会再发 done。
                        // 落一条确认提示语，让历史连贯，也让这条 clientRequestId 的幂等记录闭环。
                        log.info("ai_stream_event type=confirm conversationId={} kind={} interruptId={}",
                                conversationId, event.get("kind"), event.get("interruptId"));
                        String prompt = event.get("prompt") instanceof String value && StringUtils.hasText(value)
                                ? value
                                : "请确认是否继续办理";
                        saveMessage(conversationId, userId, clientRequestId, "assistant", prompt,
                                confirmationMetadata(event));
                        terminal.set(true);
                        emitter.complete();
                    } else if ("error".equals(type)) {
                        log.warn("ai_stream_event type=error conversationId={} code={} message={}",
                                conversationId, event.get("code"), event.get("message"));
                        terminal.set(true);
                        emitter.complete();
                    }
                });
                if (terminal.compareAndSet(false, true)) {
                    sendError(emitter, "AI_STREAM_INCOMPLETE", "AI 流式响应意外结束");
                    emitter.complete();
                }
                } catch (Exception ex) {
                    log.warn("AI 流式聊天失败 conversationId={}: {}", conversationId, ex.getMessage());
                    if (terminal.compareAndSet(false, true)) {
                        sendError(emitter, "AI_STREAM_FAILED",
                                ex.getMessage() == null ? "AI 流式聊天失败" : ex.getMessage());
                        emitter.complete();
                    }
                } finally {
                    lock.close();
                }
            });
        } catch (RuntimeException ex) {
            lock.close();
            throw ex;
        }
        upstreamTask.set(task);
        if (abort.get()) {
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

    private SseEmitter immediateErrorStream(String code, String message) {
        SseEmitter emitter = new SseEmitter(10_000L);
        streamExecutor.submit(() -> {
            sendError(emitter, code, message);
            emitter.complete();
        });
        return emitter;
    }

    private ConversationExecutionLock.Handle acquireConversationLock(Long userId, String conversationId) {
        return conversationExecutionLock.tryAcquire(userId, conversationId).orElse(null);
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
        return saveMessage(conversationId, userId, clientRequestId, role, content, null);
    }

    private boolean saveMessage(String conversationId, Long userId, String clientRequestId,
            String role, String content, String metadataJson) {
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
            message.setMetadataJson(metadataJson);
            return chatMessageRepository.insert(message) > 0;
        } catch (DuplicateKeyException ex) {
            return false;
        } catch (Exception ex) {
            log.warn("保存 AI 对话消息失败: {}", ex.getMessage());
            return false;
        }
    }

    private String confirmationMetadata(Map<String, Object> event) {
        try {
            Map<String, Object> confirm = new LinkedHashMap<>();
            confirm.put("kind", event.get("kind"));
            confirm.put("prompt", event.get("prompt"));
            confirm.put("detail", event.get("detail"));
            confirm.put("conversationId", event.get("conversationId"));
            confirm.put("interruptId", event.get("interruptId"));
            Map<String, Object> metadata = new LinkedHashMap<>();
            metadata.put("status", "confirming");
            metadata.put("confirm", confirm);
            return JSON.writeValueAsString(metadata);
        } catch (Exception ex) {
            log.warn("序列化确认状态失败 conversationId={}: {}",
                    event.get("conversationId"), ex.getMessage());
            return null;
        }
    }

    private Long resolveConversationPatient(String conversationId, Long userId, Long requestedPatientId) {
        AiConversation existing = conversationRepository.selectByUserIdAndConversationId(userId, conversationId);
        if (existing != null && existing.getPatientId() != null) {
            patientAccess.assertAccess(existing.getPatientId());
            if (requestedPatientId != null && !requestedPatientId.equals(existing.getPatientId())) {
                throw new BusinessException("该会话已绑定其他患者，请新开会话");
            }
            return existing.getPatientId();
        }
        return patientAccess.resolvePatientId(requestedPatientId);
    }

    @FunctionalInterface
    private interface StreamAction {
        void run(Consumer<Map<String, Object>> consumer);
    }
}
