package com.wenrun.repository;

import com.wenrun.entity.ChatMessage;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;

/**
 * chat_messages 表 Mapper
 */
@Mapper
public interface ChatMessageRepository {

    /** 按会话ID倒序查询消息列表（前端回显历史对话） */
    List<ChatMessage> selectByConversationId(@Param("conversationId") String conversationId);

    /** 插入一条消息 */
    int insert(ChatMessage message);

    boolean existsByConversationIdAndUserId(@Param("conversationId") String conversationId,
                                            @Param("userId") Long userId);

    boolean existsByConversationId(@Param("conversationId") String conversationId);

    int deleteByConversationId(@Param("conversationId") String conversationId);
}
