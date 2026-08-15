package com.wenrun.ai.knowledge.service;

import com.wenrun.ai.knowledge.client.KnowledgeAiClient;
import com.wenrun.ai.knowledge.entity.AiKnowledgeDocument;
import com.wenrun.repository.AiKnowledgeDocumentRepository;
import com.wenrun.ai.knowledge.model.KnowledgeBaseType;
import com.wenrun.ai.knowledge.model.KnowledgeDocumentStatus;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.nio.file.Path;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class KnowledgeTaskServiceTest {

    @Mock
    private AiKnowledgeDocumentRepository mapper;
    @Mock
    private KnowledgeFileStorage storage;
    @Mock
    private KnowledgeAiClient client;

    private KnowledgeTaskService taskService;
    private AiKnowledgeDocument document;

    @BeforeEach
    void setUp() {
        taskService = new KnowledgeTaskService(mapper, storage, client);
        document = new AiKnowledgeDocument();
        document.setDocumentId("doc-1");
        document.setKnowledgeBase(KnowledgeBaseType.MEDICAL_GENERAL);
        document.setStoragePath("medical-general/source.pdf");
        document.setOriginalName("source.pdf");
        document.setStatus(KnowledgeDocumentStatus.PROCESSING);
    }

    @Test
    void marksDocumentReadyAfterSuccessfulIngest() {
        Path source = Path.of("source.pdf");
        when(mapper.selectByDocumentIdAndKnowledgeBase("doc-1", KnowledgeBaseType.MEDICAL_GENERAL))
                .thenReturn(document);
        when(storage.resolve(document.getStoragePath())).thenReturn(source);
        when(client.ingest(document, source))
                .thenReturn(new KnowledgeAiClient.IngestResult("doc-1", "medical-general", 7));

        taskService.ingest("doc-1", KnowledgeBaseType.MEDICAL_GENERAL);

        verify(mapper).updateStatus(eq("doc-1"), eq(KnowledgeBaseType.MEDICAL_GENERAL),
                eq(KnowledgeDocumentStatus.READY), eq(7), eq(null), any(), eq(null));
    }

    @Test
    void marksDocumentFailedWithoutDeletingSourceAfterIngestError() {
        Path source = Path.of("source.pdf");
        when(mapper.selectByDocumentIdAndKnowledgeBase("doc-1", KnowledgeBaseType.MEDICAL_GENERAL))
                .thenReturn(document);
        when(storage.resolve(document.getStoragePath())).thenReturn(source);
        when(client.ingest(document, source)).thenThrow(new RuntimeException("embedding key leaked-value"));

        taskService.ingest("doc-1", KnowledgeBaseType.MEDICAL_GENERAL);

        verify(mapper).updateStatus(eq("doc-1"), eq(KnowledgeBaseType.MEDICAL_GENERAL),
                eq(KnowledgeDocumentStatus.FAILED), eq(0), any(String.class), eq(null), eq(null));
        verify(storage, never()).delete(any());
    }

    @Test
    void deletesSourceOnlyAfterVectorDeletionSucceeds() {
        document.setStatus(KnowledgeDocumentStatus.DELETING);
        when(mapper.selectByDocumentIdAndKnowledgeBase("doc-1", KnowledgeBaseType.MEDICAL_GENERAL))
                .thenReturn(document);

        taskService.delete("doc-1", KnowledgeBaseType.MEDICAL_GENERAL);

        verify(client).delete(KnowledgeBaseType.MEDICAL_GENERAL, "doc-1");
        verify(storage).delete(document.getStoragePath());
        verify(mapper).updateStatus(eq("doc-1"), eq(KnowledgeBaseType.MEDICAL_GENERAL),
                eq(KnowledgeDocumentStatus.DELETED), eq(0), eq(null), eq(null), any());
    }

    @Test
    void keepsSourceAndMarksDeleteFailedWhenVectorDeletionFails() {
        document.setStatus(KnowledgeDocumentStatus.DELETING);
        when(mapper.selectByDocumentIdAndKnowledgeBase("doc-1", KnowledgeBaseType.MEDICAL_GENERAL))
                .thenReturn(document);
        org.mockito.Mockito.doThrow(new RuntimeException("qdrant unavailable"))
                .when(client).delete(KnowledgeBaseType.MEDICAL_GENERAL, "doc-1");

        taskService.delete("doc-1", KnowledgeBaseType.MEDICAL_GENERAL);

        verify(storage, never()).delete(any());
        verify(mapper).updateStatus(eq("doc-1"), eq(KnowledgeBaseType.MEDICAL_GENERAL),
                eq(KnowledgeDocumentStatus.DELETE_FAILED), eq(0), any(String.class), eq(null), eq(null));
    }
}
