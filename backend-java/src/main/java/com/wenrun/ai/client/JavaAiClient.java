package com.wenrun.ai.client;

import com.wenrun.ai.dto.AiUserContextDTO;
import com.wenrun.ai.dto.JavaChatRequestDTO;
import com.wenrun.ai.dto.PythonChatRequestDTO;
import com.wenrun.ai.exception.AiServiceException;
import com.wenrun.ai.vo.ChatResponseVO;
import com.wenrun.ai.vo.JavaChatResponseVO;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;
import java.util.UUID;

/**
 * [Java 集成] 调用 Python FastAPI {@code /java/*} 接口的专用客户端。
 */
@Component
public class JavaAiClient {

    private final AiServiceClient aiServiceClient;

    public JavaAiClient(AiServiceClient aiServiceClient) {
        this.aiServiceClient = aiServiceClient;
    }

    /**
     * 兼容旧 Java Chat DTO，但统一复用 Python 的 /v1/chat 契约，避免维护一个不存在的 /java/chat 路由。
     */
    public JavaChatResponseVO chat(JavaChatRequestDTO request, String delegationToken) {
        validateContent(request != null ? request.getContent() : null, "消息不能为空");
        request.setContent(request.getContent().trim());
        String conversationId = StringUtils.hasText(request.getSessionId())
                ? request.getSessionId()
                : "java-" + UUID.randomUUID();
        Long userId = parseUserId(request.getUserId());
        ChatResponseVO response = aiServiceClient.chat(
                new PythonChatRequestDTO(
                        request.getContent(),
                        conversationId,
                        true,
                        new AiUserContextDTO(userId, null)),
                delegationToken);
        return toLegacyResponse(request, response, conversationId);
    }

    private static JavaChatResponseVO toLegacyResponse(
            JavaChatRequestDTO request, ChatResponseVO response, String conversationId) {
        JavaChatResponseVO legacy = new JavaChatResponseVO();
        legacy.setUserInput(request.getContent());
        legacy.setIntent(response == null ? null : response.getIntent());
        legacy.setTargetAgent(response == null ? null : response.getIntent());
        legacy.setFinalOutput(response == null ? null : response.getReply());
        legacy.setSessionId(response != null && StringUtils.hasText(response.getConversationId())
                ? response.getConversationId() : conversationId);
        return legacy;
    }

    private static Long parseUserId(String value) {
        if (!StringUtils.hasText(value)) {
            return null;
        }
        try {
            return Long.valueOf(value);
        } catch (NumberFormatException ignored) {
            return null;
        }
    }

    private static void validateContent(String content, String message) {
        if (!StringUtils.hasText(content)) {
            throw new AiServiceException(message);
        }
    }
}
