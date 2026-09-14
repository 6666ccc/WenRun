package com.wenrun.ai.service;

import com.wenrun.entity.AiConversation;
import com.wenrun.common.exception.BusinessException;
import com.wenrun.common.ResultCode;
import com.wenrun.repository.AiConversationRepository;
import com.wenrun.repository.ChatMessageRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
public class ConversationOwnershipService {

    private final AiConversationRepository conversationRepository;
    private final ChatMessageRepository chatMessageRepository;

    public void establishIfAbsent(String conversationId, Long userId, Long patientId) {
        if (conversationId == null || userId == null) {
            throw new BusinessException(ResultCode.UNAUTHORIZED, "无权访问该会话");
        }
        AiConversation conversation = new AiConversation();
        conversation.setConversationId(conversationId);
        conversation.setUserId(userId);
        conversation.setPatientId(patientId);
        conversationRepository.insertIfAbsent(conversation);

        if (conversationRepository.selectByUserIdAndConversationId(userId, conversationId) == null) {
            throw new BusinessException(ResultCode.SERVICE_UNAVAILABLE, "会话暂时无法建立，请稍后重试");
        }
    }

    public void assertOwned(String conversationId, Long userId) {
        if (conversationId == null || userId == null) {
            throw new BusinessException(ResultCode.UNAUTHORIZED, "无权访问该会话");
        }
        if (conversationRepository.selectByUserIdAndConversationId(userId, conversationId) == null) {
            // 不查询其他用户作用域，避免通过错误差异泄漏 conversationId 是否存在。
            throw new BusinessException(ResultCode.NOT_FOUND, "会话不存在或已过期");
        }
    }

    @Transactional
    public void delete(String conversationId, Long userId) {
        if (conversationId == null || userId == null) {
            throw new BusinessException(ResultCode.UNAUTHORIZED, "无权访问该会话");
        }
        // 删除是幂等操作，但始终只作用于当前用户的复合键。
        conversationRepository.softDeleteByUserIdAndConversationId(userId, conversationId);
        chatMessageRepository.deleteByConversationIdAndUserId(conversationId, userId);
    }
}
