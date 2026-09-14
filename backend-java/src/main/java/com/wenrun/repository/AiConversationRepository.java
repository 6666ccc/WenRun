package com.wenrun.repository;

import com.wenrun.entity.AiConversation;
import com.wenrun.ai.vo.AiConversationVO;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

@Mapper
public interface AiConversationRepository {
    int insertIfAbsent(AiConversation conversation);

    AiConversation selectByUserIdAndConversationId(@Param("userId") Long userId,
                                                    @Param("conversationId") String conversationId);

    int softDeleteByUserIdAndConversationId(@Param("userId") Long userId,
                                            @Param("conversationId") String conversationId);

    java.util.List<AiConversationVO> selectSummariesByUserId(
            @Param("userId") Long userId,
            @Param("offset") int offset,
            @Param("limit") int limit);
}
