package com.wenrun.ai.knowledge.model;

import com.wenrun.common.exception.BusinessException;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

class KnowledgeBaseTypeTest {

    @Test
    void parsesSupportedPathValues() {
        assertEquals(KnowledgeBaseType.MEDICAL_GENERAL,
                KnowledgeBaseType.fromPath("medical-general"));
        assertEquals(KnowledgeBaseType.HOSPITAL_CUSTOM,
                KnowledgeBaseType.fromPath("hospital-custom"));
    }

    @Test
    void exposesStableQdrantCollectionNames() {
        assertEquals("wenrun_medical_general",
                KnowledgeBaseType.MEDICAL_GENERAL.getCollectionName());
        assertEquals("wenrun_hospital_custom",
                KnowledgeBaseType.HOSPITAL_CUSTOM.getCollectionName());
    }

    @Test
    void rejectsUnknownPathValues() {
        assertThrows(BusinessException.class,
                () -> KnowledgeBaseType.fromPath("other"));
    }
}
