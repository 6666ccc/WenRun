package com.wenrun.ai.service;

import com.wenrun.common.ResultCode;
import com.wenrun.common.exception.BusinessException;
import com.wenrun.entity.AiConversation;
import com.wenrun.repository.AiConversationRepository;
import com.wenrun.repository.ChatMessageRepository;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.argThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class ConversationOwnershipServiceTest {

    private final AiConversationRepository conversationRepository =
            mock(AiConversationRepository.class);
    private final ChatMessageRepository chatMessageRepository =
            mock(ChatMessageRepository.class);
    private final ConversationOwnershipService service =
            new ConversationOwnershipService(conversationRepository, chatMessageRepository);

    @Test
    void establishAtomicallyCreatesUserScopedConversation() {
        AiConversation persisted = new AiConversation();
        persisted.setUserId(3L);
        persisted.setConversationId("shared-id");
        when(conversationRepository.selectByUserIdAndConversationId(3L, "shared-id"))
                .thenReturn(persisted);

        service.establishIfAbsent("shared-id", 3L, 9L);

        verify(conversationRepository).insertIfAbsent(argThat(value ->
                value.getUserId().equals(3L)
                        && value.getConversationId().equals("shared-id")
                        && value.getPatientId().equals(9L)));
    }

    @Test
    void sameConversationIdCanBeEstablishedInTwoUserScopes() {
        AiConversation first = new AiConversation();
        first.setUserId(3L);
        first.setConversationId("shared-id");
        AiConversation second = new AiConversation();
        second.setUserId(4L);
        second.setConversationId("shared-id");
        when(conversationRepository.selectByUserIdAndConversationId(3L, "shared-id"))
                .thenReturn(first);
        when(conversationRepository.selectByUserIdAndConversationId(4L, "shared-id"))
                .thenReturn(second);

        assertDoesNotThrow(() -> service.establishIfAbsent("shared-id", 3L, 9L));
        assertDoesNotThrow(() -> service.establishIfAbsent("shared-id", 4L, 10L));
    }

    @Test
    void establishFailsClosedWhenConversationCannotBeReadBack() {
        BusinessException ex = assertThrows(BusinessException.class,
                () -> service.establishIfAbsent("broken", 3L, 9L));

        assertEquals(ResultCode.SERVICE_UNAVAILABLE, ex.getCode());
        assertEquals("会话暂时无法建立，请稍后重试", ex.getMessage());
    }

    @Test
    void deleteAllowsConversationThatWasNeverPersisted() {
        assertDoesNotThrow(() -> service.delete("session_local_only", 3L));

        verify(chatMessageRepository)
                .deleteByConversationIdAndUserId("session_local_only", 3L);
        verify(conversationRepository)
                .softDeleteByUserIdAndConversationId(3L, "session_local_only");
    }

    @Test
    void resumeRequiresAnAuthoritativeUserScopedConversation() {
        BusinessException ex = assertThrows(BusinessException.class,
                () -> service.assertOwned("missing", 3L));

        assertEquals(ResultCode.NOT_FOUND, ex.getCode());
        assertEquals("会话不存在或已过期", ex.getMessage());
    }

    @Test
    void nullIdentityIsRejected() {
        BusinessException ex = assertThrows(BusinessException.class,
                () -> service.assertOwned("session", null));

        assertEquals(ResultCode.UNAUTHORIZED, ex.getCode());
        assertEquals("无权访问该会话", ex.getMessage());
    }
}
