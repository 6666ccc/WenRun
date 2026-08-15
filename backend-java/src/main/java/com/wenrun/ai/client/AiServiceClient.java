package com.wenrun.ai.client;

import com.wenrun.ai.config.AiServiceProperties;
import com.wenrun.ai.dto.ChatRequestDTO;
import com.wenrun.ai.exception.AiServiceException;
import com.wenrun.ai.vo.ChatResponseVO;
import com.wenrun.ai.vo.ChatStreamEventVO;
import com.fasterxml.jackson.databind.ObjectMapper;
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

/**
 * AI 服务客户端，调用 Python FastAPI（/v1/chat 聊天、健康检查）。
 * <p>
 * Java 集成聊天见 {@link JavaAiClient}。
 */
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

    /**
     * 调用 FastAPI {@code POST /v1/chat}，请求体会夹带用户/患者上下文，响应 {@code {"reply": "..."}}。
     */
    public ChatResponseVO chat(ChatRequestDTO request) {
        if (request == null || !StringUtils.hasText(request.getMessage())) {
            throw new AiServiceException("消息不能为空");
        }
        request.setMessage(request.getMessage().trim());

        log.debug("调用 AI 聊天: POST {}{}", properties.getBaseUrl(), properties.getChatPath());
        try {
            ChatResponseVO response = aiRestClient.post()
                    .uri(properties.getChatPath())
                    .contentType(MediaType.APPLICATION_JSON)
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

    /**
     * 调用 FastAPI {@code POST /v1/chat/stream}，按 SSE 行解析并回调消费者。
     */
    public void streamChat(ChatRequestDTO request, ChatStreamConsumer consumer) {
        if (request == null || !StringUtils.hasText(request.getMessage())) {
            throw new AiServiceException("消息不能为空");
        }
        request.setMessage(request.getMessage().trim());

        log.debug("流式调用 AI: POST {}{}", properties.getBaseUrl(), properties.getChatStreamPath());
        try {
            aiStreamRestClient.post()
                    .uri(properties.getChatStreamPath())
                    .contentType(MediaType.APPLICATION_JSON)
                    .accept(MediaType.TEXT_EVENT_STREAM)
                    .body(request)
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

    public ChatResponseVO chat(String message) {
        ChatRequestDTO request = new ChatRequestDTO();
        request.setMessage(message);
        return chat(request);
    }

    /**
     * 探测 FastAPI {@code GET /health}，返回 {@code {"status":"ok"}} 时视为可用。
     */
    public boolean isHealthy() {
        try {
            Map<String, String> body = aiRestClient.get()
                    .uri(properties.getHealthPath())
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
}
