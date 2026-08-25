package com.wenrun.ai.service;

import com.wenrun.common.ResultCode;
import com.wenrun.common.exception.BusinessException;
import com.wenrun.repository.ChatMessageRepository;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class ConversationOwnershipServiceTest {

    private final ChatMessageRepository chatMessageRepository = mock(ChatMessageRepository.class);
    private final ConversationOwnershipService service = new ConversationOwnershipService(chatMessageRepository);

    @Test
    void deleteAllowsConversationThatWasNeverPersisted() {
        when(chatMessageRepository.existsByConversationId("session_local_only")).thenReturn(false);

        assertDoesNotThrow(() -> service.assertOwned("session_local_only", 3L));
    }

    @Test
    void deleteRejectsConversationOwnedByAnotherUser() {
        when(chatMessageRepository.existsByConversationId("session_other")).thenReturn(true);
        when(chatMessageRepository.existsByConversationIdAndUserId("session_other", 3L)).thenReturn(false);

        BusinessException ex = assertThrows(BusinessException.class,
                () -> service.assertOwned("session_other", 3L));
        assertEquals(ResultCode.FORBIDDEN, ex.getCode());
        assertEquals("无权访问该会话", ex.getMessage());
    }

    @Test
    void deleteAllowsConversationOwnedByCurrentUser() {
        when(chatMessageRepository.existsByConversationId("session_mine")).thenReturn(true);
        when(chatMessageRepository.existsByConversationIdAndUserId("session_mine", 3L)).thenReturn(true);

        assertDoesNotThrow(() -> service.assertOwned("session_mine", 3L));
    }
}
