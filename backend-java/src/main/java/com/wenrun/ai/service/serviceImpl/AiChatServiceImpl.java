package com.wenrun.ai.service.serviceImpl;

import com.wenrun.ai.client.AiServiceClient;
import com.wenrun.ai.client.ChatStreamConsumer;
import com.wenrun.ai.client.JavaAiClient;
import com.wenrun.ai.dto.ChatRequestDTO;
import com.wenrun.ai.dto.JavaChatRequestDTO;
import com.wenrun.ai.service.AiChatService;
import com.wenrun.ai.vo.ChatResponseVO;
import com.wenrun.ai.vo.JavaChatResponseVO;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

@Service
@RequiredArgsConstructor
public class AiChatServiceImpl implements AiChatService {

    private final AiServiceClient aiServiceClient;
    private final JavaAiClient javaAiClient;

    @Override
    public ChatResponseVO chat(ChatRequestDTO dto) {
        return aiServiceClient.chat(dto);
    }

    @Override
    public void streamChat(ChatRequestDTO dto, ChatStreamConsumer consumer) {
        aiServiceClient.streamChat(dto, consumer);
    }

    @Override
    public JavaChatResponseVO javaChat(JavaChatRequestDTO dto) {
        return javaAiClient.chat(dto);
    }
}
