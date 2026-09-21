package com.wenrun.ai.service;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.wenrun.ai.vo.aiRequest;
import com.wenrun.ai.vo.aiResumeRequest;
import com.wenrun.common.ResultCode;
import com.wenrun.common.exception.BusinessException;
import com.wenrun.config.RequestTrace;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.function.Consumer;

/** Java 到 Python AI 服务的统一网关。 */
@Slf4j
@Service
public class aiService {

    private static final int DEFAULT_CONNECT_TIMEOUT_MILLIS = 5_000;
    private static final int DEFAULT_READ_TIMEOUT_MILLIS = 300_000;
    private static final TypeReference<LinkedHashMap<String, Object>> EVENT_TYPE =
            new TypeReference<>() { };

    private final RestClient pythonClient;
    private final String apiKey;
    private final ObjectMapper objectMapper;

    @Autowired
    public aiService(
            RestClient.Builder restClientBuilder,
            ObjectMapper objectMapper,
            @Value("${AI_SERVICE_BASE_URL:http://localhost:8000}") String baseUrl,
            @Value("${AI_SERVICE_API_KEY:}") String apiKey,
            @Value("${AI_SERVICE_CONNECT_TIMEOUT_MILLIS:" + DEFAULT_CONNECT_TIMEOUT_MILLIS + "}")
            int connectTimeoutMillis,
            @Value("${AI_SERVICE_READ_TIMEOUT_MILLIS:" + DEFAULT_READ_TIMEOUT_MILLIS + "}")
            int readTimeoutMillis) {
        SimpleClientHttpRequestFactory requestFactory = new SimpleClientHttpRequestFactory();
        requestFactory.setConnectTimeout(Math.max(1, connectTimeoutMillis));
        requestFactory.setReadTimeout(Math.max(1, readTimeoutMillis));

        this.pythonClient = restClientBuilder
                .baseUrl(baseUrl)
                .requestFactory(requestFactory)
                .build();
        this.apiKey = apiKey;
        this.objectMapper = objectMapper;
    }

    /** 仅供不访问真实网络的单元测试使用。 */
    aiService(RestClient pythonClient, String apiKey) {
        this.pythonClient = pythonClient;
        this.apiKey = apiKey;
        this.objectMapper = new ObjectMapper();
    }

    public void streamChat(aiRequest request, Consumer<Map<String, Object>> consumer) {
        postStream("/v1/chat/stream", buildChatPayload(request), request.getRequestId(),
                request.getDelegatedToken(), consumer);
    }

    /** 恢复被挂起的那一轮。委托令牌是本次请求重新签发的，Python 侧节点重跑时会读到它。 */
    public void streamResume(aiResumeRequest request, Consumer<Map<String, Object>> consumer) {
        postStream("/v1/chat/resume", buildResumePayload(request), request.getRequestId(),
                request.getDelegatedToken(), consumer);
    }

    /** 删除会话时清理 Python 侧的 checkpoint。记忆清理失败不应阻塞用户删除操作。 */
    public void deleteConversationMemory(String conversationId, Long userId) {
        if (!StringUtils.hasText(conversationId) || userId == null) {
            return;
        }
        try {
            pythonClient.delete()
                    .uri(uriBuilder -> uriBuilder
                            .path("/v1/chat/memory/{conversationId}")
                            .queryParam("userId", userId)
                            .build(conversationId))
                    .headers(headers -> {
                        if (StringUtils.hasText(apiKey)) {
                            headers.set("X-Api-Key", apiKey);
                        }
                        String requestId = RequestTrace.get();
                        if (RequestTrace.isUsable(requestId)) {
                            headers.set(RequestTrace.HEADER_NAME, requestId);
                        }
                    })
                    .retrieve()
                    .toBodilessEntity();
        } catch (Exception ex) {
            log.warn("清理会话记忆失败 userId={} conversationId={}: {}",
                    userId, conversationId, ex.getMessage());
        }
    }

    private void postStream(String path, Object payload, String requestId, String delegatedToken,
                            Consumer<Map<String, Object>> consumer) {
        if (consumer == null) {
            throw new IllegalArgumentException("流式事件处理器不能为空");
        }
        try {
            RestClient.RequestBodySpec call = authenticated(pythonClient.post()
                    .uri(path)
                    .contentType(MediaType.APPLICATION_JSON)
                    .accept(MediaType.TEXT_EVENT_STREAM), requestId, delegatedToken);
            call.body(payload).exchange((request, response) -> {
                if (response.getStatusCode().isError()) {
                    throw new BusinessException(ResultCode.SERVICE_UNAVAILABLE,
                            "AI 流式服务响应异常: HTTP " + response.getStatusCode().value());
                }
                InputStream body = response.getBody();
                if (body == null) {
                    throw new IOException("AI 流式服务返回空响应体");
                }
                try (BufferedReader reader = new BufferedReader(new InputStreamReader(
                        body, StandardCharsets.UTF_8))) {
                    readSseEvents(reader, consumer);
                }
                return null;
            });
        } catch (BusinessException ex) {
            throw ex;
        } catch (RestClientException ex) {
            throw unavailable("无法连接 AI 流式服务，请确认 Python 服务已启动", ex);
        } catch (Exception ex) {
            throw unavailable("AI 流式响应解析失败", ex);
        }
    }

    /**
     * 按 SSE 事件边界解析上游响应。一个事件可以包含多行 data，最后一个事件即使
     * 上游没有再补空行也必须被消费。
     */
    private void readSseEvents(BufferedReader reader, Consumer<Map<String, Object>> consumer)
            throws IOException {
        StringBuilder data = new StringBuilder();
        String line;
        while ((line = reader.readLine()) != null) {
            if (line.isEmpty()) {
                dispatchSseData(data, consumer);
                data.setLength(0);
                continue;
            }
            if (line.startsWith(":")) {
                continue;
            }
            if (line.startsWith("data:")) {
                if (data.length() > 0) {
                    data.append('\n');
                }
                String value = line.substring("data:".length());
                if (value.startsWith(" ")) {
                    value = value.substring(1);
                }
                data.append(value);
            }
        }
        dispatchSseData(data, consumer);
    }

    private void dispatchSseData(StringBuilder data, Consumer<Map<String, Object>> consumer)
            throws IOException {
        String json = data.toString().trim();
        if (json.isEmpty() || "[DONE]".equals(json)) {
            return;
        }
        Map<String, Object> event = objectMapper.readValue(json, EVENT_TYPE);
        if (event.get("type") != null) {
            consumer.accept(event);
        }
    }

    private Map<String, Object> buildChatPayload(aiRequest request) {
        if (request == null || !StringUtils.hasText(request.getMessage())) {
            throw new BusinessException(ResultCode.BAD_REQUEST, "消息不能为空");
        }
        String conversationId = StringUtils.hasText(request.getConversationId())
                ? request.getConversationId().trim()
                : "java-" + UUID.randomUUID();
        request.setConversationId(conversationId);

        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("message", request.getMessage().trim());
        payload.put("conversationId", conversationId);
        payload.put("memoryEnabled", request.getMemoryEnabled() == null
                ? Boolean.TRUE : request.getMemoryEnabled());
        payload.put("fastMode", request.getFastMode() != null && request.getFastMode());
        if (!Boolean.FALSE.equals(request.getMemoryEnabled())
                && request.getRecoveryMessages() != null && !request.getRecoveryMessages().isEmpty()) {
            List<Map<String, Object>> recoveryMessages = request.getRecoveryMessages().stream()
                    .filter(message -> "user".equals(message.getRole()) || "assistant".equals(message.getRole()))
                    .map(message -> {
                        Map<String, Object> item = new LinkedHashMap<>();
                        item.put("id", message.getId());
                        item.put("role", message.getRole());
                        item.put("content", message.getContent());
                        item.put("createTime", message.getCreateTime());
                        return item;
                    })
                    .toList();
            if (!recoveryMessages.isEmpty()) {
                payload.put("recoveryMessages", recoveryMessages);
            }
        }
        if (request.getLongTermMemories() != null && !request.getLongTermMemories().isEmpty()) {
            List<Map<String, Object>> memories = request.getLongTermMemories().stream()
                    .limit(20)
                    .map(memory -> {
                        Map<String, Object> item = new LinkedHashMap<>();
                        item.put("memoryId", memory.getMemoryId());
                        item.put("type", memory.getType());
                        item.put("content", memory.getContent());
                        item.put("status", memory.getStatus());
                        item.put("updateTime", memory.getUpdateTime());
                        return item;
                    })
                    .toList();
            payload.put("longTermMemories", memories);
        }
        addUserContext(payload, request.getUserId(), request.getPatientId());
        return payload;
    }

    private Map<String, Object> buildResumePayload(aiResumeRequest request) {
        if (request == null || !StringUtils.hasText(request.getConversationId())) {
            throw new BusinessException(ResultCode.BAD_REQUEST, "会话 ID 不能为空");
        }
        String decision = request.getDecision();
        if (!"approve".equals(decision) && !"reject".equals(decision)) {
            throw new BusinessException(ResultCode.BAD_REQUEST, "确认结果只能是 approve 或 reject");
        }

        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("conversationId", request.getConversationId().trim());
        payload.put("decision", decision);
        if (StringUtils.hasText(request.getInterruptId())) {
            payload.put("interruptId", request.getInterruptId().trim());
        }
        addUserContext(payload, request.getUserId(), request.getPatientId());
        return payload;
    }

    private void addUserContext(Map<String, Object> payload, Long userId, Long patientId) {
        if (userId == null && patientId == null) {
            return;
        }
        Map<String, Object> context = new LinkedHashMap<>();
        if (userId != null) {
            context.put("userId", userId);
            context.put("operatorUserId", userId);
        }
        if (patientId != null) {
            context.put("patientId", patientId);
        }
        payload.put("userContext", context);
    }

    private RestClient.RequestBodySpec authenticated(
            RestClient.RequestBodySpec call, String requestId, String delegatedToken) {
        if (StringUtils.hasText(apiKey)) {
            call = call.header("X-Api-Key", apiKey);
        }
        if (StringUtils.hasText(delegatedToken)) {
            call = call.header("X-Delegated-Token", delegatedToken);
        }
        if (RequestTrace.isUsable(requestId)) {
            call = call.header(RequestTrace.HEADER_NAME, requestId);
        }
        return call;
    }

    private BusinessException unavailable(String message, Exception cause) {
        BusinessException exception = new BusinessException(ResultCode.SERVICE_UNAVAILABLE, message);
        exception.initCause(cause);
        return exception;
    }
}
