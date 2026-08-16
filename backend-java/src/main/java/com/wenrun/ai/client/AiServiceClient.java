package com.wenrun.ai.client;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.wenrun.ai.config.AiServiceProperties;
import com.wenrun.ai.dto.ChatRequestDTO;
import com.wenrun.ai.dto.ChatResumeRequestDTO;
import com.wenrun.ai.dto.PythonChatRequestDTO;
import com.wenrun.ai.exception.AiServiceException;
import com.wenrun.ai.vo.ChatResponseVO;
import com.wenrun.ai.vo.ChatStreamEventVO;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.HttpStatusCode;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.Map;

@Slf4j
@Component
public class AiServiceClient {

    private static final ParameterizedTypeReference<Map<String, String>> HEALTH_BODY =
            new ParameterizedTypeReference<>() {
            };

    private final RestClient aiRestClient;
    private final RestClient aiStreamRestClient;
    private final AiServiceProperties properties;
    private final ObjectMapper objectMapper;

    public AiServiceClient(
            @Qualifier("aiRestClient") RestClient aiRestClient,
            @Qualifier("aiStreamRestClient") RestClient aiStreamRestClient,
            AiServiceProperties properties,
            ObjectMapper objectMapper) {
        this.aiRestClient = aiRestClient;
        this.aiStreamRestClient = aiStreamRestClient;
        this.properties = properties;
        this.objectMapper = objectMapper;
    }

    public ChatResponseVO chat(ChatRequestDTO request) {
        return chat(toPythonRequest(request), null);
    }

    public ChatResponseVO chat(PythonChatRequestDTO request, String delegationToken) {
        if (request == null || !StringUtils.hasText(request.message())) {
            throw new AiServiceException("消息不能为空");
        }
        try {
            ChatResponseVO response = withAuth(aiRestClient.post()
                    .uri(properties.getChatPath())
                    .contentType(MediaType.APPLICATION_JSON), delegationToken)
                    .body(request)
                    .retrieve()
                    .onStatus(HttpStatusCode::isError, (req, res) -> {
                        String detail = AiClientSupport.readBody(res.getBody());
                        throw new AiServiceException(
                                "AI 服务响应异常: HTTP " + res.getStatusCode().value()
                                        + (detail.isEmpty() ? "" : " - " + detail));
                    })
                    .body(ChatResponseVO.class);
            if (response == null
                    || (!"pending".equalsIgnoreCase(response.getStatus())
                    && response.getReply() == null)) {
                throw new AiServiceException("AI 服务返回为空");
            }
            return response;
        } catch (AiServiceException ex) {
            throw ex;
        } catch (RestClientException ex) {
            throw new AiServiceException("无法连接 AI 服务，请确认 FastAPI 已启动", ex);
        }
    }

    public void streamChat(ChatRequestDTO request, ChatStreamConsumer consumer) {
        streamChat(toPythonRequest(request), null, consumer);
    }

    public void streamChat(PythonChatRequestDTO request, String delegationToken, ChatStreamConsumer consumer) {
        if (request == null || !StringUtils.hasText(request.message())) {
            throw new AiServiceException("消息不能为空");
        }
        postStream(properties.getChatStreamPath(), request, delegationToken, consumer);
    }

    public void resumeStream(ChatResumeRequestDTO request, String delegationToken, ChatStreamConsumer consumer) {
        if (request == null || !StringUtils.hasText(request.getConversationId())) {
            throw new AiServiceException("恢复请求不完整");
        }
        postStream(properties.getChatResumeStreamPath(), request, delegationToken, consumer);
    }

    public void deleteConversation(String conversationId) {
        try {
            withAuth(aiRestClient.delete()
                    .uri("/v1/chat/conversations/{id}", conversationId), null)
                    .retrieve()
                    .toBodilessEntity();
        } catch (RestClientException ex) {
            throw new AiServiceException("无法删除 AI 会话", ex);
        }
    }

    public ChatResponseVO chat(String message) {
        ChatRequestDTO request = new ChatRequestDTO();
        request.setMessage(message);
        return chat(request);
    }

    public boolean isHealthy() {
        try {
            Map<String, String> body = withAuth(aiRestClient.get().uri(properties.getHealthPath()), null)
                    .retrieve()
                    .onStatus(HttpStatusCode::isError, (req, res) -> {
                        throw new AiServiceException(
                                "AI 健康检查失败: HTTP " + res.getStatusCode().value());
                    })
                    .body(HEALTH_BODY);
            return body != null && "ok".equalsIgnoreCase(body.get("status"));
        } catch (RestClientException ex) {
            log.debug("AI 服务不可用: {}", ex.getMessage());
            return false;
        }
    }

    private void postStream(String path, Object body, String delegationToken, ChatStreamConsumer consumer) {
        try {
            withAuth(aiStreamRestClient.post()
                    .uri(path)
                    .contentType(MediaType.APPLICATION_JSON)
                    .accept(MediaType.TEXT_EVENT_STREAM), delegationToken)
                    .body(body)
                    .exchange((req, res) -> {
                        if (res.getStatusCode().isError()) {
                            String detail = AiClientSupport.readBody(res.getBody());
                            throw new AiServiceException(
                                    "AI 流式服务响应异常: HTTP " + res.getStatusCode().value()
                                            + (detail.isEmpty() ? "" : " - " + detail));
                        }
                        try (BufferedReader reader = new BufferedReader(
                                new InputStreamReader(res.getBody(), StandardCharsets.UTF_8))) {
                            String line;
                            while ((line = reader.readLine()) != null) {
                                if (!line.startsWith("data:")) {
                                    continue;
                                }
                                String payload = line.substring(5).trim();
                                if (payload.isEmpty()) {
                                    continue;
                                }
                                ChatStreamEventVO event = objectMapper.readValue(
                                        payload, ChatStreamEventVO.class);
                                if (event != null && event.getType() != null) {
                                    consumer.accept(event);
                                }
                            }
                        }
                        return null;
                    });
        } catch (AiServiceException ex) {
            throw ex;
        } catch (Exception ex) {
            if (ex instanceof RestClientException restEx) {
                throw new AiServiceException("无法连接 AI 流式服务，请确认 FastAPI 已启动", restEx);
            }
            throw new AiServiceException("AI 流式响应解析失败", ex);
        }
    }

    private RestClient.RequestBodySpec withAuth(RestClient.RequestBodySpec spec, String delegationToken) {
        if (StringUtils.hasText(properties.getApiKey())) {
            spec = spec.header("X-Api-Key", properties.getApiKey());
        }
        if (StringUtils.hasText(delegationToken)) {
            spec = spec.header("X-Delegated-Token", delegationToken);
        }
        return spec;
    }

    private RestClient.RequestHeadersSpec<?> withAuth(RestClient.RequestHeadersSpec<?> spec, String delegationToken) {
        if (StringUtils.hasText(properties.getApiKey())) {
            spec = spec.header("X-Api-Key", properties.getApiKey());
        }
        if (StringUtils.hasText(delegationToken)) {
            spec = spec.header("X-Delegated-Token", delegationToken);
        }
        return spec;
    }

    private static PythonChatRequestDTO toPythonRequest(ChatRequestDTO request) {
        String message = request.getMessage() == null ? null : request.getMessage().trim();
        return new PythonChatRequestDTO(
                message,
                request.getConversationId(),
                request.getMemoryEnabled(),
                new com.wenrun.ai.dto.AiUserContextDTO(null, null)
        );
    }
}
