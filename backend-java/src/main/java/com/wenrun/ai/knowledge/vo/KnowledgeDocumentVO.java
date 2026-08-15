package com.wenrun.ai.knowledge.vo;

import com.wenrun.ai.knowledge.model.KnowledgeDocumentStatus;
import lombok.Data;

import java.time.LocalDateTime;

@Data
public class KnowledgeDocumentVO {
    private String documentId;
    private String knowledgeBase;
    private String originalName;
    private String contentType;
    private Long fileSize;
    private KnowledgeDocumentStatus status;
    private Integer chunkCount;
    private String errorMessage;
    private Long uploadedBy;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
    private LocalDateTime completedAt;
}
