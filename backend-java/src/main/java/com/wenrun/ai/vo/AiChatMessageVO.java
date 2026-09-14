package com.wenrun.ai.vo;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.wenrun.entity.ChatMessage;
import lombok.Data;

import java.time.LocalDateTime;
import java.util.Map;

@Data
public class AiChatMessageVO {
    private static final ObjectMapper JSON = new ObjectMapper();

    private Long id;
    private String role;
    private String content;
    private String clientRequestId;
    private LocalDateTime createTime;
    private Map<String, Object> metadata;

    public static AiChatMessageVO from(ChatMessage message) {
        AiChatMessageVO value = new AiChatMessageVO();
        value.setId(message.getId());
        value.setRole(message.getRole());
        value.setContent(message.getContent());
        value.setClientRequestId(message.getClientRequestId());
        value.setCreateTime(message.getCreateTime());
        if (message.getMetadataJson() != null && !message.getMetadataJson().isBlank()) {
            try {
                value.setMetadata(JSON.readValue(
                        message.getMetadataJson(), new TypeReference<Map<String, Object>>() { }));
            } catch (Exception ignored) {
                value.setMetadata(Map.of());
            }
        } else {
            value.setMetadata(Map.of());
        }
        return value;
    }
}
