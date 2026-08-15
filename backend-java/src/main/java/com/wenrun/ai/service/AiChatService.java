package com.wenrun.ai.service;

import com.wenrun.ai.client.ChatStreamConsumer;
import com.wenrun.ai.dto.ChatRequestDTO;
import com.wenrun.ai.dto.JavaChatRequestDTO;
import com.wenrun.ai.vo.ChatResponseVO;
import com.wenrun.ai.vo.JavaChatResponseVO;

public interface AiChatService {

    ChatResponseVO chat(ChatRequestDTO dto);

    void streamChat(ChatRequestDTO dto, ChatStreamConsumer consumer);

    /** Java 集成聊天：转发 FastAPI {@code /java/chat} */
    JavaChatResponseVO javaChat(JavaChatRequestDTO dto);
}
