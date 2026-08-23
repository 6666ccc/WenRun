package com.wenrun.ai.service;

import com.wenrun.ai.vo.aiReply;
import com.wenrun.ai.vo.aiRequest;
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
import org.springframework.web.client.RestClientResponseException;

import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;

/**
 * Java 侧 AI 对话服务：把患者消息转发到 Python AI 服务，并统一转换错误。
 */
@Slf4j
@Service
public class aiService {

    private static final int DEFAULT_CONNECT_TIMEOUT_MILLIS = 5_000;
    private static final int DEFAULT_READ_TIMEOUT_MILLIS = 90_000;

    /** 指向 Python AI 服务的 HTTP 客户端，基址来自 AI_SERVICE_BASE_URL。 */
    private final RestClient pythonClient;
    /** 调用 Python 时使用的 API Key；未配置则不加认证头。 */
    private final String apiKey;

    /**
     * 注入 RestClient 与 Python 服务地址、密钥。
     *
     * @param restClientBuilder Spring 提供的 RestClient 构建器
     * @param baseUrl           Python 服务根地址，默认 http://localhost:8000
     * @param apiKey            可选的服务间 API Key
     * @param connectTimeoutMillis 建立到 Python 服务连接的最长时间
     * @param readTimeoutMillis    等待图执行结果的最长时间
     */
    @Autowired
    public aiService(
            RestClient.Builder restClientBuilder,
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
    }

    /**
     * 仅用于同包测试：注入已配置好的客户端，避免测试发起真实网络请求。
     */
    aiService(RestClient pythonClient, String apiKey) {
        this.pythonClient = pythonClient;
        this.apiKey = apiKey;
    }

    /**
     * 将患者消息转发给 Python 的 POST /v1/chat 接口。
     *
     * <p>
     * 未带会话 ID 时会生成 {@code java-} 前缀的 UUID，便于 Python 侧区分来源。
     * </p>
     */
    public aiReply chat(aiRequest request) {
        if (request == null || !StringUtils.hasText(request.getMessage())) {
            throw new BusinessException(ResultCode.BAD_REQUEST, "消息不能为空");
        }

        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("message", request.getMessage().trim());
        payload.put("conversationId", StringUtils.hasText(request.getConversationId())
                ? request.getConversationId().trim()
                : "java-" + UUID.randomUUID());
        if (request.getMemoryEnabled() != null) {
            payload.put("memoryEnabled", request.getMemoryEnabled());
        }

        try {
            RestClient.RequestBodySpec call = pythonClient.post()
                    .uri("/v1/chat")
                    .contentType(MediaType.APPLICATION_JSON)
                    .accept(MediaType.APPLICATION_JSON)
                    .body(payload);
            if (StringUtils.hasText(apiKey)) {
                call.header("X-Api-Key", apiKey);
            }
            // 透传当前请求追踪号，便于 Java / Python 日志对齐
            String requestId = RequestTrace.get();
            if (RequestTrace.isUsable(requestId)) {
                call.header(RequestTrace.HEADER_NAME, requestId);
            }

            aiReply reply = call.retrieve().body(aiReply.class);
            if (reply == null) {
                throw new BusinessException(ResultCode.SERVICE_UNAVAILABLE, "AI 服务返回为空");
            }
            return reply;
        } catch (BusinessException ex) {
            throw ex;
        } catch (RestClientResponseException ex) {
            // HTTP 已到达但对端返回 4xx/5xx
            log.warn("Python AI 服务返回错误: status={}", ex.getStatusCode().value());
            throw new BusinessException(ResultCode.SERVICE_UNAVAILABLE,
                    "AI 服务暂时不可用，请稍后重试");
        } catch (RestClientException ex) {
            // 连接失败、超时等未拿到 HTTP 响应的情况
            log.warn("无法连接 Python AI 服务: {}", ex.getMessage());
            throw new BusinessException(ResultCode.SERVICE_UNAVAILABLE,
                    "无法连接 AI 服务，请确认 Python 服务已启动");
        }
    }
}
