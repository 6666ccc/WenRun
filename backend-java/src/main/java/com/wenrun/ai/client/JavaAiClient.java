package com.wenrun.ai.client;

import com.wenrun.ai.config.AiServiceProperties;
import com.wenrun.ai.dto.JavaChatRequestDTO;
import com.wenrun.ai.exception.AiServiceException;
import com.wenrun.ai.vo.JavaChatResponseVO;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.http.HttpStatusCode;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;

/**
 * [Java 集成] 调用 Python FastAPI {@code /java/*} 接口的专用客户端。
 */
@Slf4j
@Component
public class JavaAiClient {

    private final RestClient aiRestClient;
    private final AiServiceProperties properties;

    public JavaAiClient(
            @Qualifier("aiRestClient") RestClient aiRestClient,
            AiServiceProperties properties) {
        this.aiRestClient = aiRestClient;
        this.properties = properties;
    }

    /** 调用 {@code POST /java/chat}，走 LangGraph 路由 + Agent。 */
    public JavaChatResponseVO chat(JavaChatRequestDTO request) {
        validateContent(request != null ? request.getContent() : null, "消息不能为空");
        request.setContent(request.getContent().trim());

        log.debug("[JavaAi] chat: POST {}{}", properties.getBaseUrl(), properties.getJavaChatPath());
        return postForJavaChatResponse(properties.getJavaChatPath(), request, "Java 集成聊天");
    }

    private JavaChatResponseVO postForJavaChatResponse(String path, Object body, String actionLabel) {
        try {
            JavaChatResponseVO response = aiRestClient.post()
                    .uri(path)
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(body)
                    .retrieve()
                    .onStatus(HttpStatusCode::isError, (req, res) -> {
                        String detail = AiClientSupport.readBody(res.getBody());
                        throw new AiServiceException(
                                actionLabel + "异常: HTTP " + res.getStatusCode().value()
                                        + (detail.isEmpty() ? "" : " - " + detail));
                    })
                    .body(JavaChatResponseVO.class);
            if (response == null) {
                throw new AiServiceException(actionLabel + "返回为空");
            }
            return response;
        } catch (AiServiceException ex) {
            throw ex;
        } catch (RestClientException ex) {
            throw new AiServiceException("无法连接 AI 服务，请确认 FastAPI 已启动", ex);
        }
    }

    private static void validateContent(String content, String message) {
        if (!StringUtils.hasText(content)) {
            throw new AiServiceException(message);
        }
    }
}
