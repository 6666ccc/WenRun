package com.wenrun.ai.service;

import com.wenrun.ai.vo.AiMemoryWriteRequest;
import com.wenrun.common.ResultCode;
import com.wenrun.common.exception.BusinessException;
import com.wenrun.entity.AiPatientMemory;
import com.wenrun.repository.AiPatientMemoryRepository;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.argThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class AiPatientMemoryServiceTest {
    private final AiPatientMemoryRepository repository = mock(AiPatientMemoryRepository.class);
    private final AiPatientMemoryService service = new AiPatientMemoryService(repository);

    @Test
    void createsOnlyAnAllowedExplicitPreferenceWithSource() {
        AiMemoryWriteRequest request = request("communication_preference", "请用简短中文",  null);

        AiPatientMemory created = service.createConfirmed(12L, request);

        assertEquals(12L, created.getPatientId());
        assertEquals("active", created.getStatus());
        verify(repository).insert(argThat(memory ->
                memory.getPatientId().equals(12L)
                        && memory.getSourceConversationId().equals("conversation-1")
                        && memory.getConfidence().intValue() == 1));
    }

    @Test
    void rejectsClinicalFactsAndDoseContent() {
        BusinessException diagnosis = assertThrows(BusinessException.class,
                () -> service.createConfirmed(12L,
                        request("communication_preference", "诊断：高血压", null)));
        BusinessException dose = assertThrows(BusinessException.class,
                () -> service.createConfirmed(12L,
                        request("appointment_preference", "每天服用 20mg", null)));
        BusinessException allergy = assertThrows(BusinessException.class,
                () -> service.createConfirmed(12L,
                        request("communication_preference", "我对青霉素过敏", null)));
        BusinessException symptom = assertThrows(BusinessException.class,
                () -> service.createConfirmed(12L,
                        request("accessibility_need", "我最近胸痛", null)));

        assertEquals(ResultCode.BAD_REQUEST, diagnosis.getCode());
        assertEquals(ResultCode.BAD_REQUEST, dose.getCode());
        assertEquals(ResultCode.BAD_REQUEST, allergy.getCode());
        assertEquals(ResultCode.BAD_REQUEST, symptom.getCode());
    }

    @Test
    void updateCreatesANewRevisionAndSupersedesTheExpectedVersion() {
        AiPatientMemory current = new AiPatientMemory();
        current.setMemoryId("memory-1");
        current.setPatientId(12L);
        current.setVersion(2);
        current.setStatus("active");
        current.setSourceConversationId("trusted-conversation");
        current.setSourceMessageId(41L);
        when(repository.selectLatestForUpdate(12L, "memory-1")).thenReturn(current);

        AiMemoryWriteRequest requested = request("communication_preference", "回复详细", 2);
        requested.setSourceConversationId("spoofed-conversation");
        requested.setSourceMessageId(999L);
        AiPatientMemory updated = service.update(12L, "memory-1", requested);

        assertEquals(3, updated.getVersion());
        assertEquals("trusted-conversation", updated.getSourceConversationId());
        assertEquals(41L, updated.getSourceMessageId());
        verify(repository).markSuperseded(12L, "memory-1", 2);
        verify(repository).insert(updated);
    }

    @Test
    void activeRecallIsAlwaysPatientScoped() {
        when(repository.selectActiveByPatientId(12L, 5)).thenReturn(List.of());

        service.listActive(12L, 5);

        verify(repository).selectActiveByPatientId(12L, 5);
    }

    private AiMemoryWriteRequest request(String type, String content, Integer version) {
        AiMemoryWriteRequest request = new AiMemoryWriteRequest();
        request.setType(type);
        request.setContent(content);
        request.setSourceConversationId("conversation-1");
        request.setSourceMessageId(101L);
        request.setExpectedVersion(version);
        return request;
    }
}
