package com.wenrun.ai.knowledge.entity;

import com.wenrun.ai.knowledge.model.KnowledgeBaseType;
import com.wenrun.ai.knowledge.model.KnowledgeDocumentStatus;
import lombok.Data;

import java.time.LocalDateTime;

@Data
public class AiKnowledgeDocument {
    private Long id;
    private String documentId;
    private KnowledgeBaseType knowledgeBase;
    private String originalName;
    private String storagePath;
    private String contentType;
    private Long fileSize;
    private String fileSha256;
    private KnowledgeDocumentStatus status;
    private Integer chunkCount;
    private String errorMessage;
    private Long uploadedBy;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
    private LocalDateTime completedAt;
    private LocalDateTime deletedAt;
}
