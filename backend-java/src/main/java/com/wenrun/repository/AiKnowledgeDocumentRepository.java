package com.wenrun.repository;

import com.wenrun.ai.knowledge.entity.AiKnowledgeDocument;
import com.wenrun.ai.knowledge.model.KnowledgeBaseType;
import com.wenrun.ai.knowledge.model.KnowledgeDocumentStatus;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.time.LocalDateTime;
import java.util.List;

@Mapper
public interface AiKnowledgeDocumentRepository {

    int insert(AiKnowledgeDocument document);

    AiKnowledgeDocument selectByDocumentIdAndKnowledgeBase(
            @Param("documentId") String documentId,
            @Param("knowledgeBase") KnowledgeBaseType knowledgeBase);

    int countActiveByDigest(
            @Param("knowledgeBase") KnowledgeBaseType knowledgeBase,
            @Param("fileSha256") String fileSha256);

    long countByFilter(
            @Param("knowledgeBase") KnowledgeBaseType knowledgeBase,
            @Param("status") KnowledgeDocumentStatus status);

    List<AiKnowledgeDocument> selectPageByFilter(
            @Param("knowledgeBase") KnowledgeBaseType knowledgeBase,
            @Param("status") KnowledgeDocumentStatus status,
            @Param("offset") int offset,
            @Param("pageSize") int pageSize);

    int updateStatus(
            @Param("documentId") String documentId,
            @Param("knowledgeBase") KnowledgeBaseType knowledgeBase,
            @Param("status") KnowledgeDocumentStatus status,
            @Param("chunkCount") Integer chunkCount,
            @Param("errorMessage") String errorMessage,
            @Param("completedAt") LocalDateTime completedAt,
            @Param("deletedAt") LocalDateTime deletedAt);

    List<AiKnowledgeDocument> selectStaleProcessing(@Param("before") LocalDateTime before);
}
