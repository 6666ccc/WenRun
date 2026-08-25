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

    public void establishIfAbsent(String conversationId, Long userId) {
        if (conversationId == null || userId == null) {
            throw new BusinessException(ResultCode.UNAUTHORIZED, "无权访问该会话");
        }
        if (chatMessageRepository.existsByConversationId(conversationId)
                && !chatMessageRepository.existsByConversationIdAndUserId(conversationId, userId)) {
            throw new BusinessException(ResultCode.FORBIDDEN, "无权访问该会话");
        }
    }

    public void assertOwned(String conversationId, Long userId) {
        if (conversationId == null || userId == null) {
            throw new BusinessException(ResultCode.UNAUTHORIZED, "无权访问该会话");
        }
        // 前端会话先写在本地。从未落库或已经删掉时，删除应视为成功，而不是 403。
        if (!chatMessageRepository.existsByConversationId(conversationId)) {
            return;
        }
        if (!chatMessageRepository.existsByConversationIdAndUserId(conversationId, userId)) {
            throw new BusinessException(ResultCode.FORBIDDEN, "无权访问该会话");
        }
    }
}
