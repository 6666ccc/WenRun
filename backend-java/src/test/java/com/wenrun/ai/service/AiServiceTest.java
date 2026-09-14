package com.wenrun.ai.service;

import com.wenrun.ai.vo.aiRequest;
import com.wenrun.ai.vo.aiResumeRequest;
import com.wenrun.common.ResultCode;
import com.wenrun.common.exception.BusinessException;
import com.wenrun.entity.AiPatientMemory;
import com.wenrun.entity.ChatMessage;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestClient;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.header;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.jsonPath;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.method;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withServerError;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withSuccess;

class AiServiceTest {

    @Test
    void parsesPythonSseEvents() {
        RestClient.Builder builder = RestClient.builder().baseUrl("http://python.test");
        MockRestServiceServer server = MockRestServiceServer.bindTo(builder).build();
        aiService service = new aiService(builder.build(), "service-key");
        server.expect(requestTo("http://python.test/v1/chat/stream"))
                .andExpect(method(HttpMethod.POST))
                .andExpect(header("X-Api-Key", "service-key"))
                .andExpect(header("X-Request-Id", "request-123"))
                .andExpect(jsonPath("$.userContext.userId").value(7))
                .andExpect(jsonPath("$.userContext.patientId").value(12))
                .andExpect(jsonPath("$.fastMode").value(true))
                .andExpect(jsonPath("$.recoveryMessages[0].id").value(91))
                .andExpect(jsonPath("$.recoveryMessages[0].role").value("user"))
                .andExpect(jsonPath("$.recoveryMessages[0].content").value("上一轮问题"))
                .andExpect(jsonPath("$.longTermMemories[0].memoryId").value("memory-1"))
                .andExpect(jsonPath("$.longTermMemories[0].type").value("communication_preference"))
                .andExpect(jsonPath("$.longTermMemories[0].content").value("请用简短中文"))
                .andRespond(withSuccess("""
                        data: {"type":"status","content":"正在分析"}

                        data: {"type":"token","content":"联调成功"}

                        data: {"type":"done","reply":"联调成功","conversationId":"conversation-1"}

                        """, MediaType.TEXT_EVENT_STREAM));

        aiRequest request = new aiRequest();
        request.setMessage("测试流式响应");
        request.setConversationId("conversation-1");
        request.setUserId(7L);
        request.setPatientId(12L);
        request.setFastMode(true);
        request.setRequestId("request-123");
        ChatMessage recoveryMessage = new ChatMessage();
        recoveryMessage.setId(91L);
        recoveryMessage.setRole("user");
        recoveryMessage.setContent("上一轮问题");
        request.setRecoveryMessages(List.of(recoveryMessage));
        AiPatientMemory memory = new AiPatientMemory();
        memory.setMemoryId("memory-1");
        memory.setType("communication_preference");
        memory.setContent("请用简短中文");
        memory.setStatus("active");
        request.setLongTermMemories(List.of(memory));
        List<Map<String, Object>> events = new ArrayList<>();

        service.streamChat(request, events::add);

        assertEquals(List.of("status", "token", "done"),
                events.stream().map(event -> event.get("type")).toList());
        assertEquals("联调成功", events.get(2).get("reply"));
        server.verify();
    }

    @Test
    void parsesMultilineSseDataAndFlushesFinalEvent() {
        RestClient.Builder builder = RestClient.builder().baseUrl("http://python.test");
        MockRestServiceServer server = MockRestServiceServer.bindTo(builder).build();
        aiService service = new aiService(builder.build(), "");
        server.expect(requestTo("http://python.test/v1/chat/stream"))
                .andExpect(jsonPath("$.recoveryMessages").doesNotExist())
                .andRespond(withSuccess("""
                        : keep-alive
                        data: {"type":"token",
                        data: "content":"第一段"}

                        data: {"type":"done","reply":"第一段"}""", MediaType.TEXT_EVENT_STREAM));

        aiRequest request = new aiRequest();
        request.setMessage("测试 SSE 解析");
        request.setMemoryEnabled(false);
        ChatMessage ignoredRecovery = new ChatMessage();
        ignoredRecovery.setId(92L);
        ignoredRecovery.setRole("user");
        ignoredRecovery.setContent("禁用记忆时不得发送");
        request.setRecoveryMessages(List.of(ignoredRecovery));
        List<Map<String, Object>> events = new ArrayList<>();

        service.streamChat(request, events::add);

        assertEquals(List.of("token", "done"),
                events.stream().map(event -> event.get("type")).toList());
        assertEquals("第一段", events.get(0).get("content"));
        server.verify();
    }

    @Test
    void convertsPythonStreamErrorsToServiceUnavailable() {
        RestClient.Builder builder = RestClient.builder().baseUrl("http://python.test");
        MockRestServiceServer server = MockRestServiceServer.bindTo(builder).build();
        aiService service = new aiService(builder.build(), "");
        server.expect(requestTo("http://python.test/v1/chat/stream"))
                .andExpect(method(HttpMethod.POST))
                .andRespond(withServerError());

        aiRequest request = new aiRequest();
        request.setMessage("你好");

        BusinessException exception = assertThrows(
                BusinessException.class,
                () -> service.streamChat(request, event -> { }));

        assertEquals(ResultCode.SERVICE_UNAVAILABLE, exception.getCode());
        server.verify();
    }

    @Test
    void forwardsResumeDecisionToPython() {
        RestClient.Builder builder = RestClient.builder().baseUrl("http://python.test");
        MockRestServiceServer server = MockRestServiceServer.bindTo(builder).build();
        aiService service = new aiService(builder.build(), "service-key");
        server.expect(requestTo("http://python.test/v1/chat/resume"))
                .andExpect(method(HttpMethod.POST))
                .andExpect(header("X-Api-Key", "service-key"))
                .andExpect(header("X-Delegated-Token", "delegated-token"))
                .andExpect(jsonPath("$.conversationId").value("conversation-1"))
                .andExpect(jsonPath("$.decision").value("approve"))
                .andExpect(jsonPath("$.interruptId").value("int-1"))
                .andExpect(jsonPath("$.userContext.patientId").value(12))
                .andRespond(withSuccess("""
                        data: {"type":"done","reply":"挂号已办好。","conversationId":"conversation-1"}

                        """, MediaType.TEXT_EVENT_STREAM));

        aiResumeRequest request = new aiResumeRequest();
        request.setConversationId("conversation-1");
        request.setDecision("approve");
        request.setInterruptId("int-1");
        request.setUserId(7L);
        request.setPatientId(12L);
        request.setDelegatedToken("delegated-token");
        List<Map<String, Object>> events = new ArrayList<>();

        service.streamResume(request, events::add);

        assertEquals(List.of("done"), events.stream().map(event -> event.get("type")).toList());
        server.verify();
    }

    @Test
    void resumeRejectsBlankDecision() {
        RestClient.Builder builder = RestClient.builder().baseUrl("http://python.test");
        aiService service = new aiService(builder.build(), "");

        aiResumeRequest request = new aiResumeRequest();
        request.setConversationId("conversation-1");

        BusinessException exception = assertThrows(
                BusinessException.class,
                () -> service.streamResume(request, event -> { }));

        assertEquals(ResultCode.BAD_REQUEST, exception.getCode());
    }
}
