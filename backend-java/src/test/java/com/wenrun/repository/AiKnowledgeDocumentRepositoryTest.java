package com.wenrun.repository;

import com.wenrun.ai.knowledge.entity.AiKnowledgeDocument;
import com.wenrun.ai.knowledge.model.KnowledgeBaseType;
import com.wenrun.ai.knowledge.model.KnowledgeDocumentStatus;
import org.junit.jupiter.api.Test;
import org.mybatis.spring.boot.test.autoconfigure.MybatisTest;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.test.context.jdbc.Sql;

import java.time.LocalDateTime;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;

@MybatisTest
@Sql(scripts = "/schema-knowledge.sql")
class AiKnowledgeDocumentRepositoryTest {

    @Autowired
    private AiKnowledgeDocumentRepository mapper;

    @Test
    void insertsAndFindsDocumentWithinKnowledgeBase() {
        AiKnowledgeDocument document = document("doc-medical", KnowledgeBaseType.MEDICAL_GENERAL,
                "digest-medical", KnowledgeDocumentStatus.PROCESSING);

        assertEquals(1, mapper.insert(document));
        assertNotNull(document.getId());

        AiKnowledgeDocument found = mapper.selectByDocumentIdAndKnowledgeBase(
                "doc-medical", KnowledgeBaseType.MEDICAL_GENERAL);
        assertEquals("medical.pdf", found.getOriginalName());
        assertEquals(KnowledgeDocumentStatus.PROCESSING, found.getStatus());
    }

    @Test
    void filtersPagesAndDetectsOnlyActiveDuplicateDigests() {
        mapper.insert(document("doc-ready", KnowledgeBaseType.MEDICAL_GENERAL,
                "same-digest", KnowledgeDocumentStatus.READY));
        mapper.insert(document("doc-deleted", KnowledgeBaseType.MEDICAL_GENERAL,
                "deleted-digest", KnowledgeDocumentStatus.DELETED));
        mapper.insert(document("doc-hospital", KnowledgeBaseType.HOSPITAL_CUSTOM,
                "hospital-digest", KnowledgeDocumentStatus.READY));

        assertEquals(1, mapper.countByFilter(
                KnowledgeBaseType.MEDICAL_GENERAL, KnowledgeDocumentStatus.READY));
        List<AiKnowledgeDocument> records = mapper.selectPageByFilter(
                KnowledgeBaseType.MEDICAL_GENERAL, KnowledgeDocumentStatus.READY, 0, 10);
        assertEquals(List.of("doc-ready"),
                records.stream().map(AiKnowledgeDocument::getDocumentId).toList());
        assertEquals(1, mapper.countActiveByDigest(
                KnowledgeBaseType.MEDICAL_GENERAL, "same-digest"));
        assertEquals(0, mapper.countActiveByDigest(
                KnowledgeBaseType.MEDICAL_GENERAL, "deleted-digest"));
    }

    private static AiKnowledgeDocument document(
            String documentId,
            KnowledgeBaseType knowledgeBase,
            String digest,
            KnowledgeDocumentStatus status) {
        AiKnowledgeDocument document = new AiKnowledgeDocument();
        document.setDocumentId(documentId);
        document.setKnowledgeBase(knowledgeBase);
        document.setOriginalName("medical.pdf");
        document.setStoragePath("medical-general/file.pdf");
        document.setContentType("application/pdf");
        document.setFileSize(128L);
        document.setFileSha256(digest);
        document.setStatus(status);
        document.setChunkCount(0);
        document.setUploadedBy(1L);
        document.setCreatedAt(LocalDateTime.now());
        document.setUpdatedAt(LocalDateTime.now());
        if (status == KnowledgeDocumentStatus.DELETED) {
            document.setDeletedAt(LocalDateTime.now());
        }
        return document;
    }
}
