package com.example.wenrun.ai.service;

import com.example.wenrun.ai.client.ChatStreamConsumer;
import com.example.wenrun.ai.dto.ChatRequestDTO;
import com.example.wenrun.ai.dto.JavaChatRequestDTO;
import com.example.wenrun.ai.vo.ChatResponseVO;
import com.example.wenrun.ai.vo.JavaChatResponseVO;

public interface AiChatService {

    ChatResponseVO chat(ChatRequestDTO dto);

    void streamChat(ChatRequestDTO dto, ChatStreamConsumer consumer);

    /** Java 集成聊天：转发 FastAPI {@code /java/chat} */
    JavaChatResponseVO javaChat(JavaChatRequestDTO dto);
}
