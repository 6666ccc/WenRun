package com.wenrun.repository;

import com.wenrun.entity.ChatMessage;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;

@Mapper
public interface ChatMessageRepository {
    List<ChatMessage> selectByConversationId(@Param("conversationId") String conversationId);

    int insert(ChatMessage message);

    boolean existsByConversationIdAndUserId(@Param("conversationId") String conversationId,
                                            @Param("userId") Long userId);

    boolean existsByConversationId(@Param("conversationId") String conversationId);

    int deleteByConversationId(@Param("conversationId") String conversationId);
}
