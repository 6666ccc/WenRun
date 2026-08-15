package com.wenrun.ai.knowledge.controller;

import com.wenrun.ai.knowledge.model.KnowledgeBaseType;
import com.wenrun.ai.knowledge.model.KnowledgeDocumentStatus;
import com.wenrun.ai.knowledge.service.KnowledgeAdminGuard;
import com.wenrun.ai.knowledge.service.KnowledgeDocumentService;
import com.wenrun.ai.knowledge.vo.KnowledgeUploadVO;
import com.wenrun.common.exception.BusinessException;
import com.wenrun.common.exception.GlobalExceptionHandler;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.multipart;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@ExtendWith(MockitoExtension.class)
class KnowledgeDocumentControllerTest {

    @Mock
    private KnowledgeDocumentService service;
    @Mock
    private KnowledgeAdminGuard guard;

    private MockMvc mockMvc;

    @BeforeEach
    void setUp() {
        mockMvc = MockMvcBuilders.standaloneSetup(new KnowledgeDocumentController(service, guard))
                .setControllerAdvice(new GlobalExceptionHandler())
                .build();
    }

    @Test
    void uploadsToKnowledgeBaseSelectedByUrl() throws Exception {
        MockMultipartFile file = new MockMultipartFile(
                "file", "hospital.md", "text/markdown", "route".getBytes());
        when(guard.currentUserId()).thenReturn(7L);
        when(service.upload(KnowledgeBaseType.HOSPITAL_CUSTOM, file, 7L))
                .thenReturn(new KnowledgeUploadVO(
                        "doc-1", "hospital-custom", KnowledgeDocumentStatus.PROCESSING));

        mockMvc.perform(multipart(
                        "/api/ai/knowledge-bases/hospital-custom/documents").file(file))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(200))
                .andExpect(jsonPath("$.data.documentId").value("doc-1"))
                .andExpect(jsonPath("$.data.knowledgeBase").value("hospital-custom"))
                .andExpect(jsonPath("$.data.status").value("PROCESSING"));

        verify(guard).requireAdmin();
        verify(service).upload(KnowledgeBaseType.HOSPITAL_CUSTOM, file, 7L);
    }

    @Test
    void rejectsUnknownKnowledgeBasePath() throws Exception {
        MockMultipartFile file = new MockMultipartFile(
                "file", "hospital.md", "text/markdown", "route".getBytes());

        mockMvc.perform(multipart("/api/ai/knowledge-bases/unknown/documents").file(file))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(400));
    }

    @Test
    void returnsForbiddenResultWhenCallerIsNotAdmin() throws Exception {
        doThrow(new BusinessException(403, "仅管理员可管理知识库"))
                .when(guard).requireAdmin();

        mockMvc.perform(get("/api/ai/knowledge-bases/medical-general/documents"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(403));
    }

    @Test
    void scopesDeleteToKnowledgeBaseInUrl() throws Exception {
        mockMvc.perform(delete(
                        "/api/ai/knowledge-bases/medical-general/documents/doc-7"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(200));

        verify(service).delete(KnowledgeBaseType.MEDICAL_GENERAL, "doc-7");
    }
}
