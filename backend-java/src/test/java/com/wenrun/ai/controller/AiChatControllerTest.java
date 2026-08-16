package com.wenrun.ai.controller;

import com.wenrun.ai.config.AiServiceProperties;
import com.wenrun.ai.delegation.AiDelegationTokenService;
import com.wenrun.ai.dto.ChatResumeRequestDTO;
import com.wenrun.ai.service.AiChatService;
import com.wenrun.ai.service.ConversationOwnershipService;
import com.wenrun.ai.vo.ChatInterruptVO;
import com.wenrun.ai.vo.ChatStreamEventVO;
import com.wenrun.common.context.UserContext;
import com.wenrun.common.exception.BusinessException;
import com.wenrun.common.exception.GlobalExceptionHandler;
import com.wenrun.entity.Patient;
import com.wenrun.repository.ChatMessageRepository;
import com.wenrun.repository.PatientRepository;
import com.wenrun.repository.SysUserRepository;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import java.time.Duration;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.doAnswer;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.asyncDispatch;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.request;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@ExtendWith(MockitoExtension.class)
class AiChatControllerTest {

    @Mock
    private AiChatService aiChatService;
    @Mock
    private SysUserRepository sysUserRepository;
    @Mock
    private PatientRepository patientRepository;
    @Mock
    private ChatMessageRepository chatMessageRepository;
    @Mock
    private AiDelegationTokenService delegationTokenService;
    @Mock
    private ConversationOwnershipService ownershipService;

    private MockMvc mockMvc;

    @BeforeEach
    void setUp() {
        AiServiceProperties properties = new AiServiceProperties();
        properties.setStreamReadTimeout(Duration.ofSeconds(5));
        AiChatController controller = new AiChatController(
                aiChatService,
                sysUserRepository,
                patientRepository,
                chatMessageRepository,
                properties,
                delegationTokenService,
                ownershipService);
        mockMvc = MockMvcBuilders.standaloneSetup(controller)
                .setControllerAdvice(new GlobalExceptionHandler())
                .build();
        UserContext.setUserId(1L);
    }

    @AfterEach
    void tearDown() {
        UserContext.clear();
    }

    @Test
    void interruptCompletesStreamWithoutErrorEvent() throws Exception {
        Patient patient = new Patient();
        patient.setId(10L);
        when(patientRepository.selectByUserId(1L)).thenReturn(patient);
        when(delegationTokenService.issueReadToken(1L, 10L, "c-1")).thenReturn("read-token");
        doAnswer(invocation -> {
            ChatStreamEventVO event = new ChatStreamEventVO();
            event.setType("interrupt");
            ChatInterruptVO interrupt = new ChatInterruptVO();
            interrupt.setInterruptId("i-1");
            event.setInterrupt(interrupt);
            invocation.getArgument(2, com.wenrun.ai.client.ChatStreamConsumer.class).accept(event);
            return null;
        }).when(aiChatService).streamChat(any(), eq("read-token"), any());

        var result = mockMvc.perform(post("/api/ai/chat/stream")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"message\":\"挂号\",\"conversationId\":\"c-1\"}"))
                .andExpect(request().asyncStarted())
                .andReturn();
        mockMvc.perform(asyncDispatch(result))
                .andExpect(status().isOk());
    }

    @Test
    void resumeApprovedIssuesWriteToken() throws Exception {
        when(delegationTokenService.issueWriteToken(1L, 10L, "c-1", "i-1")).thenReturn("write-token");
        Patient patient = new Patient();
        patient.setId(10L);
        when(patientRepository.selectByUserId(1L)).thenReturn(patient);
        doAnswer(invocation -> {
            ChatStreamEventVO event = new ChatStreamEventVO();
            event.setType("done");
            event.setReply("挂号成功");
            invocation.getArgument(2, com.wenrun.ai.client.ChatStreamConsumer.class).accept(event);
            return null;
        }).when(aiChatService).resumeStream(any(), eq("write-token"), any());

        var result = mockMvc.perform(post("/api/ai/chat/resume/stream")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"conversationId\":\"c-1\",\"interruptId\":\"i-1\",\"approved\":true}"))
                .andExpect(request().asyncStarted())
                .andReturn();
        mockMvc.perform(asyncDispatch(result))
                .andExpect(status().isOk());

        verify(ownershipService).assertOwned("c-1", 1L);
        verify(delegationTokenService).issueWriteToken(1L, 10L, "c-1", "i-1");
        ArgumentCaptor<ChatResumeRequestDTO> captor = ArgumentCaptor.forClass(ChatResumeRequestDTO.class);
        verify(aiChatService).resumeStream(captor.capture(), eq("write-token"), any());
        assertEquals("i-1", captor.getValue().getInterruptId());
    }

    @Test
    void otherUserCannotResumeConversation() throws Exception {
        org.mockito.Mockito.doThrow(new BusinessException(com.wenrun.common.ResultCode.UNAUTHORIZED, "无权访问该会话"))
                .when(ownershipService).assertOwned("c-1", 1L);

        mockMvc.perform(post("/api/ai/chat/resume/stream")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"conversationId\":\"c-1\",\"interruptId\":\"i-1\",\"approved\":true}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(401));
    }

    @Test
    void streamErrorEventIsJson() throws Exception {
        Patient patient = new Patient();
        patient.setId(10L);
        when(patientRepository.selectByUserId(1L)).thenReturn(patient);
        when(delegationTokenService.issueReadToken(1L, 10L, "c-1")).thenReturn("read-token");
        org.mockito.Mockito.doThrow(new com.wenrun.ai.exception.AiServiceException("Authorization: Bearer leaked-token"))
                .when(aiChatService).streamChat(any(), eq("read-token"), any());

        var result = mockMvc.perform(post("/api/ai/chat/stream")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"message\":\"挂号\",\"conversationId\":\"c-1\"}"))
                .andExpect(request().asyncStarted())
                .andReturn();
        mockMvc.perform(asyncDispatch(result))
                .andExpect(status().isOk())
                .andExpect(content().string(org.hamcrest.Matchers.containsString("\"type\":\"error\"")))
                .andExpect(content().string(org.hamcrest.Matchers.not(
                        org.hamcrest.Matchers.containsString("leaked-token"))));
    }
}
