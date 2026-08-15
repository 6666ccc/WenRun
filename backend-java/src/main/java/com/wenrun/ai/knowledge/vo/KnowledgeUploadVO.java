package com.wenrun.ai.knowledge.vo;

import com.wenrun.ai.knowledge.model.KnowledgeDocumentStatus;
import lombok.AllArgsConstructor;
import lombok.Data;

@Data
@AllArgsConstructor
public class KnowledgeUploadVO {
    private String documentId;
    private String knowledgeBase;
    private KnowledgeDocumentStatus status;
}
