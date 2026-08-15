package com.wenrun.ai.knowledge.service;

import com.wenrun.ai.knowledge.client.KnowledgeAiClient;
import com.wenrun.ai.knowledge.entity.AiKnowledgeDocument;
import com.wenrun.repository.AiKnowledgeDocumentRepository;
import com.wenrun.ai.knowledge.model.KnowledgeBaseType;
import com.wenrun.ai.knowledge.model.KnowledgeDocumentStatus;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;

import java.nio.file.Path;
import java.time.LocalDateTime;

@Slf4j
@Service
@RequiredArgsConstructor
public class KnowledgeTaskService {

    private final AiKnowledgeDocumentRepository mapper;
    private final KnowledgeFileStorage storage;
    private final KnowledgeAiClient client;

    @Async("knowledgeTaskExecutor")
    public void ingest(String documentId, KnowledgeBaseType knowledgeBase) {
        AiKnowledgeDocument document = mapper.selectByDocumentIdAndKnowledgeBase(documentId, knowledgeBase);
        if (document == null || document.getStatus() != KnowledgeDocumentStatus.PROCESSING) {
            return;
        }

        try {
            Path source = storage.resolve(document.getStoragePath());
            KnowledgeAiClient.IngestResult result = client.ingest(document, source);
            mapper.updateStatus(documentId, knowledgeBase, KnowledgeDocumentStatus.READY,
                    result.chunkCount(), null, LocalDateTime.now(), null);
        } catch (Exception ex) {
            log.warn("知识库文档入库失败 | documentId={} | type={}", documentId,
                    ex.getClass().getSimpleName());
            mapper.updateStatus(documentId, knowledgeBase, KnowledgeDocumentStatus.FAILED,
                    0, safeError("文档入库失败", ex), null, null);
        }
    }

    @Async("knowledgeTaskExecutor")
    public void delete(String documentId, KnowledgeBaseType knowledgeBase) {
        AiKnowledgeDocument document = mapper.selectByDocumentIdAndKnowledgeBase(documentId, knowledgeBase);
        if (document == null || document.getStatus() != KnowledgeDocumentStatus.DELETING) {
            return;
        }

        try {
            client.delete(knowledgeBase, documentId);
            storage.delete(document.getStoragePath());
            mapper.updateStatus(documentId, knowledgeBase, KnowledgeDocumentStatus.DELETED,
                    0, null, null, LocalDateTime.now());
        } catch (Exception ex) {
            log.warn("知识库文档删除失败 | documentId={} | type={}", documentId,
                    ex.getClass().getSimpleName());
            mapper.updateStatus(documentId, knowledgeBase, KnowledgeDocumentStatus.DELETE_FAILED,
                    0, safeError("文档删除失败", ex), null, null);
        }
    }

    private static String safeError(String prefix, Exception ex) {
        return prefix + "（" + ex.getClass().getSimpleName() + "）";
    }
}
