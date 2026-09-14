package com.wenrun.repository;

import com.wenrun.entity.ChatMessage;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;

@Mapper
public interface ChatMessageRepository {
    List<ChatMessage> selectByConversationIdAndUserId(
            @Param("conversationId") String conversationId,
            @Param("userId") Long userId);

    List<ChatMessage> selectRecentByConversationIdAndUserId(
            @Param("conversationId") String conversationId,
            @Param("userId") Long userId,
            @Param("limit") int limit);

    List<ChatMessage> selectPageByConversationIdAndUserId(
            @Param("conversationId") String conversationId,
            @Param("userId") Long userId,
            @Param("offset") int offset,
            @Param("limit") int limit);

    int insert(ChatMessage message);

    ChatMessage selectByClientRequestId(@Param("conversationId") String conversationId,
                                        @Param("userId") Long userId,
                                        @Param("clientRequestId") String clientRequestId,
                                        @Param("role") String role);

    int deleteByConversationIdAndUserId(@Param("conversationId") String conversationId,
                                        @Param("userId") Long userId);

    int completeLatestConfirmation(@Param("conversationId") String conversationId,
                                   @Param("userId") Long userId,
                                   @Param("interruptId") String interruptId);
}
