package com.wenrun.ai.service;

import com.wenrun.ai.client.ChatStreamConsumer;
import com.wenrun.ai.dto.ChatRequestDTO;
import com.wenrun.ai.dto.ChatResumeRequestDTO;
import com.wenrun.ai.dto.JavaChatRequestDTO;
import com.wenrun.ai.dto.PythonChatRequestDTO;
import com.wenrun.ai.vo.ChatResponseVO;
import com.wenrun.ai.vo.JavaChatResponseVO;

public interface AiChatService {

    ChatResponseVO chat(ChatRequestDTO dto);

    ChatResponseVO chat(PythonChatRequestDTO dto, String delegationToken);

    void streamChat(ChatRequestDTO dto, ChatStreamConsumer consumer);

    void streamChat(PythonChatRequestDTO dto, String delegationToken, ChatStreamConsumer consumer);

    void resumeStream(ChatResumeRequestDTO dto, String delegationToken, ChatStreamConsumer consumer);

    void deleteConversation(String conversationId);

    JavaChatResponseVO javaChat(JavaChatRequestDTO dto, String delegationToken);
}
