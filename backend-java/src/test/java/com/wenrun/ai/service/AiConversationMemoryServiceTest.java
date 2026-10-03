package com.wenrun.ai.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.wenrun.ai.concurrency.ConversationExecutionLock;
import com.wenrun.ai.security.DelegatedToolPrincipal;
import com.wenrun.ai.vo.AiSummaryCommitRequest;
import com.wenrun.common.exception.BusinessException;
import com.wenrun.entity.AiConversation;
import com.wenrun.entity.ChatMessage;
import com.wenrun.repository.AiConversationRepository;
import com.wenrun.repository.ChatMessageRepository;
import org.junit.jupiter.api.Test;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

class AiConversationMemoryServiceTest {
    private final AiConversationRepository conversations = mock(AiConversationRepository.class);
    private final ChatMessageRepository messages = mock(ChatMessageRepository.class);
    private final ConversationExecutionLock locks = mock(ConversationExecutionLock.class);
    private final ObjectMapper json = new ObjectMapper();
    private final AiConversationMemoryService service = new AiConversationMemoryService(conversations, messages, locks, json);
    private final DelegatedToolPrincipal principal = new DelegatedToolPrincipal(1L, 2L, "patient", Set.of(), "t");
    private AiConversation row(long version) {
        AiConversation row = new AiConversation();
        row.setPatientId(2L); row.setSummaryVersion(version);
        when(conversations.selectByUserIdAndConversationId(1L, "c")).thenReturn(row);
        when(locks.ownsExecution(1L, "c", "owner")).thenReturn(true);
        return row;
    }
    private AiSummaryCommitRequest request() {
        AiSummaryCommitRequest request = new AiSummaryCommitRequest();
        request.setConversationId("c"); request.setExecutionId("owner"); request.setExpectedVersion(0L);
        request.setCoveredMessageIds(List.of(3L, 4L));
        request.setSummary(new LinkedHashMap<>(Map.of("schema_version", 2, "version", 1,
            "last_message_id", 4, "patient_self_reports", List.of(Map.of("text", "体重60公斤",
                "source_message_id", 3, "source", "user_statement", "verification", "unverified")),
            "pending_tasks", List.of("确认当前体重"), "superseded_items", List.of())));
        return request;
    }
    private void prefix(String role) {
        ChatMessage first = new ChatMessage(); first.setId(3L); first.setRole(role); first.setContent("我的体重60公斤");
        ChatMessage second = new ChatMessage(); second.setId(4L); second.setRole("assistant"); second.setContent("请确认");
        when(messages.selectAfterId("c", 1L, 0L, 4L, 201)).thenReturn(List.of(first, second));
    }
    @Test void commitsOnlyOwnedContiguousGroundedPrefix() {
        row(0); prefix("user");
        when(conversations.commitSummary(eq(1L), eq("c"), eq(0L), anyString())).thenReturn(1);
        assertEquals(1L, service.commit(principal, request()).get("version"));
    }
    @Test void lostAckIsIdempotentAndDoesNotWriteAgain() throws Exception {
        AiSummaryCommitRequest request = request();
        row(1).setSummaryJson(json.writeValueAsString(request.getSummary()));
        assertEquals(4L, service.commit(principal, request).get("lastMessageId"));
        verify(conversations, never()).commitSummary(anyLong(), anyString(), anyLong(), anyString());
    }
    @Test void rejectedDatabaseWriteProducesNoAck() {
        row(0); prefix("user");
        assertThrows(BusinessException.class, () -> service.commit(principal, request()));
    }
    @Test void assistantClinicalExcerptCannotBecomePatientStatement() {
        row(0); prefix("assistant");
        assertThrows(BusinessException.class, () -> service.commit(principal, request()));
        verify(conversations, never()).commitSummary(anyLong(), anyString(), anyLong(), anyString());
    }
    @Test void anotherPatientAndLostExecutionAreRejected() {
        row(0).setPatientId(9L);
        assertThrows(BusinessException.class, () -> service.commit(principal, request()));
        row(0); when(locks.ownsExecution(1L, "c", "owner")).thenReturn(false);
        assertThrows(BusinessException.class, () -> service.commit(principal, request()));
    }
    @Test void missingCoverageAndRemovedFieldsAreRejected() {
        row(0); prefix("user");
        AiSummaryCommitRequest request = request(); request.setCoveredMessageIds(List.of(4L));
        assertThrows(BusinessException.class, () -> service.commit(principal, request));
        AiSummaryCommitRequest invalid = request(); invalid.getSummary().put("verified_business_facts", List.of());
        assertThrows(BusinessException.class, () -> service.commit(principal, invalid));
    }
}
