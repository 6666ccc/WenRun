package com.wenrun.ai.service;

import com.wenrun.common.ResultCode;
import com.wenrun.common.exception.BusinessException;
import com.wenrun.repository.ChatMessageRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

@Service
@RequiredArgsConstructor
public class ConversationOwnershipService {

    private final ChatMessageRepository chatMessageRepository;

    public void assertOwned(String conversationId, Long userId) {
        if (conversationId == null || userId == null) {
            throw new BusinessException(ResultCode.UNAUTHORIZED, "无权访问该会话");
        }
        if (!chatMessageRepository.existsByConversationIdAndUserId(conversationId, userId)) {
            throw new BusinessException(ResultCode.UNAUTHORIZED, "无权访问该会话");
        }
    }

    public void establishIfAbsent(String conversationId, Long userId) {
        if (conversationId == null || userId == null) {
            return;
        }
        if (chatMessageRepository.existsByConversationId(conversationId)
                && !chatMessageRepository.existsByConversationIdAndUserId(conversationId, userId)) {
            throw new BusinessException(ResultCode.UNAUTHORIZED, "无权访问该会话");
        }
    }
}
