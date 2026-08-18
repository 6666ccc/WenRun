package com.wenrun.ai.controller;

import com.wenrun.ai.config.AiServiceProperties;
import com.wenrun.ai.delegation.AiDelegationTokenService;
import com.wenrun.ai.dto.AiUserContextDTO;
import com.wenrun.ai.dto.ChatRequestDTO;
import com.wenrun.ai.dto.ChatResumeRequestDTO;
import com.wenrun.ai.dto.JavaChatRequestDTO;
import com.wenrun.ai.dto.PythonChatRequestDTO;
import com.wenrun.ai.exception.AiServiceException;
import com.wenrun.ai.logging.AiLogSanitizer;
import com.wenrun.ai.service.AiChatService;
import com.wenrun.ai.service.ConversationOwnershipService;
import com.wenrun.ai.vo.ChatResponseVO;
import com.wenrun.ai.vo.ChatStreamEventVO;
import com.wenrun.ai.vo.JavaChatResponseVO;
import com.wenrun.common.Result;
import com.wenrun.common.context.UserContext;
import com.wenrun.entity.ChatMessage;
import com.wenrun.entity.Patient;
import com.wenrun.repository.ChatMessageRepository;
import com.wenrun.repository.PatientRepository;
import com.wenrun.repository.SysUserRepository;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.MediaType;
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
import java.util.UUID;
import java.util.concurrent.CompletableFuture;

@Slf4j
@RestController
@RequestMapping("/api/ai")
@RequiredArgsConstructor
public class AiChatController {

    private final AiChatService aiChatService;
    private final SysUserRepository sysUserMapper;
    private final PatientRepository patientMapper;
    private final ChatMessageRepository chatMessageMapper;
    private final AiServiceProperties aiServiceProperties;
    private final AiDelegationTokenService delegationTokenService;
    private final ConversationOwnershipService ownershipService;

    @PostMapping("/chat")
    public Result<ChatResponseVO> chat(@Valid @RequestBody ChatRequestDTO dto) {
        Long userId = currentUserId();
        Long patientId = currentPatientId(userId);
        ownershipService.establishIfAbsent(dto.getConversationId(), userId);
        saveMessage(dto.getConversationId(), userId, "user", dto.getMessage());
        String token = delegationTokenService.issueReadToken(userId, patientId, dto.getConversationId());
        ChatResponseVO response = aiChatService.chat(toPythonRequest(dto, userId, patientId), token);
        if (response != null
                && "completed".equalsIgnoreCase(response.getStatus())
                && StringUtils.hasText(response.getReply())) {
            saveMessage(dto.getConversationId(), userId, "assistant", response.getReply());
        }
        return Result.success(response);
    }

    @PostMapping(value = "/chat/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public SseEmitter chatStream(@Valid @RequestBody ChatRequestDTO dto) {
        Long userId = currentUserId();
        Long patientId = currentPatientId(userId);
        ownershipService.establishIfAbsent(dto.getConversationId(), userId);
        saveMessage(dto.getConversationId(), userId, "user", dto.getMessage());
        String token = delegationTokenService.issueReadToken(userId, patientId, dto.getConversationId());
        return stream(consumer -> aiChatService.streamChat(
                toPythonRequest(dto, userId, patientId), token, consumer), dto.getConversationId(), userId);
    }

    @PostMapping(value = "/chat/resume/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public SseEmitter chatResumeStream(@Valid @RequestBody ChatResumeRequestDTO dto) {
        Long userId = currentUserId();
        Long patientId = currentPatientId(userId);
        ownershipService.assertOwned(dto.getConversationId(), userId);
        String token = Boolean.TRUE.equals(dto.getApproved())
                ? delegationTokenService.issueWriteToken(userId, patientId, dto.getConversationId(), dto.getInterruptId())
                : delegationTokenService.issueReadToken(userId, patientId, dto.getConversationId());
        return stream(consumer -> aiChatService.resumeStream(dto, token, consumer), dto.getConversationId(), userId);
    }

    @DeleteMapping("/conversations/{conversationId}")
    public Result<Void> deleteConversation(@PathVariable String conversationId) {
        Long userId = currentUserId();
        ownershipService.assertOwned(conversationId, userId);
        aiChatService.deleteConversation(conversationId);
        chatMessageMapper.deleteByConversationId(conversationId);
        return Result.success();
    }

    @PostMapping("/java/chat")
    public Result<JavaChatResponseVO> javaChat(@RequestBody JavaChatRequestDTO dto, HttpServletRequest request) {
        Long userId = currentUserId();
        if (userId != null) {
            dto.setUserId(String.valueOf(userId));
        }
        if (!StringUtils.hasText(dto.getSessionId())) {
            dto.setSessionId("java-" + UUID.randomUUID());
        }
        Long patientId = currentPatientId(userId);
        String delegationToken = userId == null
                ? null
                : delegationTokenService.issueReadToken(userId, patientId, dto.getSessionId());
        saveMessage(dto.getSessionId(), userId, "user", dto.getContent());
        JavaChatResponseVO result = aiChatService.javaChat(dto, delegationToken);
        if (result != null && result.getFinalOutput() != null) {
            saveMessage(dto.getSessionId(), userId, "assistant", result.getFinalOutput());
        }
        return Result.success(result);
    }

    private SseEmitter stream(StreamAction action, String conversationId, Long userId) {
        long timeoutMs = aiServiceProperties.getStreamReadTimeout().toMillis();
        SseEmitter emitter = new SseEmitter(timeoutMs);
        emitter.onTimeout(emitter::complete);
        emitter.onError(ex -> log.warn("SSE 连接异常: {}", ex.getMessage()));
        CompletableFuture.runAsync(() -> {
            StringBuilder fullReply = new StringBuilder();
            boolean[] completed = {false};
            try {
                action.run(event -> {
                    if (event == null || event.getType() == null) {
                        return;
                    }
                    try {
                        if ("error".equals(event.getType())) {
                            emitter.send(SseEmitter.event().data(errorPayload(event)));
                            emitter.complete();
                            completed[0] = true;
                            return;
                        }
                        emitter.send(SseEmitter.event().data(event));
                        if ("interrupt".equals(event.getType())) {
                            completed[0] = true;
                            emitter.complete();
                            return;
                        }
                        if ("token".equals(event.getType()) && event.getContent() != null) {
                            fullReply.append(event.getContent());
                        }
                        if ("done".equals(event.getType())) {
                            String reply = StringUtils.hasText(event.getReply())
                                    ? event.getReply() : fullReply.toString();
                            saveMessage(conversationId, userId, "assistant", reply);
                            emitter.complete();
                            completed[0] = true;
                        }
                    } catch (IOException ex) {
                        throw new AiServiceException("SSE 推送失败", ex);
                    }
                });
                if (!completed[0]) {
                    if (!fullReply.isEmpty()) {
                        saveMessage(conversationId, userId, "assistant", fullReply.toString());
                    }
                    emitter.complete();
                }
            } catch (Exception ex) {
                log.warn("AI 流式聊天失败: {}", AiLogSanitizer.redact(ex.getMessage()));
                try {
                    emitter.send(SseEmitter.event().data(Map.of(
                            "type", "error",
                            "code", "AI_STREAM_FAILED",
                            "message", AiLogSanitizer.redact(
                                    ex.getMessage() == null ? "AI 流式聊天失败" : ex.getMessage())
                    )));
                } catch (IOException ignored) {
                }
                emitter.complete();
            }
        });
        return emitter;
    }

    private Map<String, String> errorPayload(ChatStreamEventVO event) {
        Map<String, String> payload = new LinkedHashMap<>();
        payload.put("type", "error");
        if (event.getCode() != null) {
            payload.put("code", event.getCode());
        }
        payload.put("message", AiLogSanitizer.redact(StringUtils.hasText(event.getMessage())
                ? event.getMessage()
                : (event.getContent() == null ? "AI 流式服务异常" : event.getContent())));
        return payload;
    }

    private void saveMessage(String conversationId, Long userId, String role, String content) {
        if (conversationId == null || content == null) {
            return;
        }
        try {
            ChatMessage msg = new ChatMessage();
            msg.setConversationId(conversationId);
            msg.setUserId(userId);
            msg.setRole(role);
            msg.setContent(content);
            chatMessageMapper.insert(msg);
        } catch (Exception e) {
            log.warn("保存聊天消息失败: {}", e.getMessage());
        }
    }

    private PythonChatRequestDTO toPythonRequest(ChatRequestDTO dto, Long userId, Long patientId) {
        return new PythonChatRequestDTO(
                dto.getMessage(),
                dto.getConversationId(),
                dto.getMemoryEnabled() == null ? Boolean.TRUE : dto.getMemoryEnabled(),
                new AiUserContextDTO(userId, patientId)
        );
    }

    private Long currentUserId() {
        return UserContext.getUserId();
    }

    private Long currentPatientId(Long userId) {
        if (userId == null) {
            return null;
        }
        Patient patient = patientMapper.selectByUserId(userId);
        return patient == null ? null : patient.getId();
    }

    @FunctionalInterface
    private interface StreamAction {
        void run(com.wenrun.ai.client.ChatStreamConsumer consumer);
    }
}
