package com.wenrun.ai.knowledge.service;

import com.wenrun.ai.knowledge.config.KnowledgeTaskProperties;
import com.wenrun.ai.knowledge.entity.AiKnowledgeDocument;
import com.wenrun.repository.AiKnowledgeDocumentRepository;
import com.wenrun.ai.knowledge.model.KnowledgeBaseType;
import com.wenrun.ai.knowledge.model.KnowledgeDocumentStatus;
import com.wenrun.ai.knowledge.vo.KnowledgeUploadVO;
import com.wenrun.common.exception.BusinessException;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.jdbc.BadSqlGrammarException;
import org.springframework.mock.web.MockMultipartFile;

import java.nio.file.Path;
import java.time.Duration;
import java.util.List;
import java.sql.SQLException;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class KnowledgeDocumentServiceImplTest {

    @Mock
    private AiKnowledgeDocumentRepository mapper;
    @Mock
    private KnowledgeFileStorage storage;
    @Mock
    private KnowledgeTaskService taskService;

    private KnowledgeDocumentServiceImpl service;

    @BeforeEach
    void setUp() {
        KnowledgeTaskProperties taskProperties = new KnowledgeTaskProperties();
        taskProperties.setStaleAfter(Duration.ofMinutes(30));
        service = new KnowledgeDocumentServiceImpl(mapper, storage, taskService, taskProperties);
    }

    @Test
    void createsProcessingRecordAndSubmitsIngest() {
        MockMultipartFile file = new MockMultipartFile(
                "file", "guide.md", "text/markdown", "content".getBytes());
        when(storage.store(KnowledgeBaseType.HOSPITAL_CUSTOM, file))
                .thenReturn(new KnowledgeFileStorage.StoredKnowledgeFile(
                        Path.of("absolute.md"), Path.of("hospital-custom/source.md"), "digest", "md"));

        KnowledgeUploadVO result = service.upload(KnowledgeBaseType.HOSPITAL_CUSTOM, file, 9L);

        ArgumentCaptor<AiKnowledgeDocument> captor = ArgumentCaptor.forClass(AiKnowledgeDocument.class);
        verify(mapper).insert(captor.capture());
        AiKnowledgeDocument inserted = captor.getValue();
        assertEquals(KnowledgeDocumentStatus.PROCESSING, inserted.getStatus());
        assertEquals("guide.md", inserted.getOriginalName());
        assertEquals(9L, inserted.getUploadedBy());
        assertEquals(inserted.getDocumentId(), result.getDocumentId());
        verify(taskService).ingest(inserted.getDocumentId(), KnowledgeBaseType.HOSPITAL_CUSTOM);
    }

    @Test
    void rejectsDuplicateAndRemovesNewlyStoredCopy() {
        MockMultipartFile file = new MockMultipartFile(
                "file", "guide.md", "text/markdown", "content".getBytes());
        KnowledgeFileStorage.StoredKnowledgeFile stored = new KnowledgeFileStorage.StoredKnowledgeFile(
                Path.of("absolute.md"), Path.of("hospital-custom/source.md"), "digest", "md");
        when(storage.store(KnowledgeBaseType.HOSPITAL_CUSTOM, file)).thenReturn(stored);
        when(mapper.countActiveByDigest(KnowledgeBaseType.HOSPITAL_CUSTOM, "digest")).thenReturn(1);

        assertThrows(BusinessException.class,
                () -> service.upload(KnowledgeBaseType.HOSPITAL_CUSTOM, file, 9L));

        verify(storage).delete(stored.relativePath().toString());
        verify(mapper, never()).insert(any());
    }

    @Test
    void retriesFailedIngestAndFailedDeleteUsingCorrectTask() {
        AiKnowledgeDocument failed = document(KnowledgeDocumentStatus.FAILED);
        when(mapper.selectByDocumentIdAndKnowledgeBase("doc-1", KnowledgeBaseType.MEDICAL_GENERAL))
                .thenReturn(failed);

        service.retry(KnowledgeBaseType.MEDICAL_GENERAL, "doc-1");

        verify(mapper).updateStatus("doc-1", KnowledgeBaseType.MEDICAL_GENERAL,
                KnowledgeDocumentStatus.PROCESSING, 0, null, null, null);
        verify(taskService).ingest("doc-1", KnowledgeBaseType.MEDICAL_GENERAL);

        AiKnowledgeDocument deleteFailed = document(KnowledgeDocumentStatus.DELETE_FAILED);
        when(mapper.selectByDocumentIdAndKnowledgeBase("doc-2", KnowledgeBaseType.MEDICAL_GENERAL))
                .thenReturn(deleteFailed);

        service.retry(KnowledgeBaseType.MEDICAL_GENERAL, "doc-2");

        verify(mapper).updateStatus("doc-2", KnowledgeBaseType.MEDICAL_GENERAL,
                KnowledgeDocumentStatus.DELETING, 0, null, null, null);
        verify(taskService).delete("doc-2", KnowledgeBaseType.MEDICAL_GENERAL);
    }

    @Test
    void rejectsRetryForReadyDocument() {
        when(mapper.selectByDocumentIdAndKnowledgeBase("doc-1", KnowledgeBaseType.MEDICAL_GENERAL))
                .thenReturn(document(KnowledgeDocumentStatus.READY));

        assertThrows(BusinessException.class,
                () -> service.retry(KnowledgeBaseType.MEDICAL_GENERAL, "doc-1"));
    }

    @Test
    void marksEligibleDocumentDeletingAndSubmitsDelete() {
        when(mapper.selectByDocumentIdAndKnowledgeBase("doc-1", KnowledgeBaseType.MEDICAL_GENERAL))
                .thenReturn(document(KnowledgeDocumentStatus.READY));

        service.delete(KnowledgeBaseType.MEDICAL_GENERAL, "doc-1");

        verify(mapper).updateStatus("doc-1", KnowledgeBaseType.MEDICAL_GENERAL,
                KnowledgeDocumentStatus.DELETING, 0, null, null, null);
        verify(taskService).delete("doc-1", KnowledgeBaseType.MEDICAL_GENERAL);
    }

    @Test
    void convertsStaleProcessingRowsToFailed() {
        AiKnowledgeDocument stale = document(KnowledgeDocumentStatus.PROCESSING);
        when(mapper.selectStaleProcessing(any())).thenReturn(List.of(stale));

        service.recoverStaleProcessing();

        verify(mapper).updateStatus(eq("doc-1"), eq(KnowledgeBaseType.MEDICAL_GENERAL),
                eq(KnowledgeDocumentStatus.FAILED), eq(0), any(String.class), eq(null), eq(null));
    }

    @Test
    void skipsStartupRecoveryWhenMigrationHasNotCreatedTableYet() {
        when(mapper.selectStaleProcessing(any())).thenThrow(
                new BadSqlGrammarException("select", "select stale", new SQLException("missing table")));

        assertDoesNotThrow(service::recoverStaleProcessing);
    }

    private static AiKnowledgeDocument document(KnowledgeDocumentStatus status) {
        AiKnowledgeDocument document = new AiKnowledgeDocument();
        document.setDocumentId(status == KnowledgeDocumentStatus.DELETE_FAILED ? "doc-2" : "doc-1");
        document.setKnowledgeBase(KnowledgeBaseType.MEDICAL_GENERAL);
        document.setStatus(status);
        return document;
    }
}
