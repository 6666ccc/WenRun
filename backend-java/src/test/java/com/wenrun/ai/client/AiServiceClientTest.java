package com.wenrun.ai.client;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.wenrun.ai.config.AiServiceProperties;
import com.wenrun.ai.dto.AiUserContextDTO;
import com.wenrun.ai.dto.ChatResumeRequestDTO;
import com.wenrun.ai.dto.JavaChatRequestDTO;
import com.wenrun.ai.dto.PythonChatRequestDTO;
import com.wenrun.ai.vo.ChatStreamEventVO;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestClient;

import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.springframework.test.web.client.ExpectedCount.once;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.header;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.method;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withSuccess;

class AiServiceClientTest {

    private MockRestServiceServer server;
    private AiServiceClient client;

    @BeforeEach
    void setUp() {
        RestClient.Builder builder = RestClient.builder().baseUrl("http://localhost:8000");
        server = MockRestServiceServer.bindTo(builder).build();
        RestClient restClient = builder.build();
        AiServiceProperties properties = new AiServiceProperties();
        properties.setApiKey("internal");
        properties.setChatStreamPath("/v1/chat/stream");
        properties.setChatResumeStreamPath("/v1/chat/resume/stream");
        client = new AiServiceClient(restClient, restClient, properties, new ObjectMapper());
    }

    @Test
    void streamChatSendsApiKeyAndDelegationToken() {
        String readToken = "read-token";
        server.expect(once(), requestTo("http://localhost:8000/v1/chat/stream"))
                .andExpect(method(HttpMethod.POST))
                .andExpect(header("X-Api-Key", "internal"))
                .andExpect(header("X-Delegated-Token", readToken))
                .andRespond(withSuccess(
                        "data: {\"type\":\"interrupt\",\"interrupt\":{\"interruptId\":\"i-1\"}}\n\n",
                        MediaType.TEXT_EVENT_STREAM));

        List<ChatStreamEventVO> events = new ArrayList<>();
        client.streamChat(
                new PythonChatRequestDTO("查询号源", "c-1", true, new AiUserContextDTO(1L, 10L)),
                readToken,
                events::add);

        assertEquals("interrupt", events.get(0).getType());
        assertEquals("i-1", events.get(0).getInterrupt().getInterruptId());
        server.verify();
    }

    @Test
    void resumeStreamSendsWriteDelegationToken() {
        server.expect(once(), requestTo("http://localhost:8000/v1/chat/resume/stream"))
                .andExpect(header("X-Api-Key", "internal"))
                .andExpect(header("X-Delegated-Token", "write-token"))
                .andRespond(withSuccess(
                        "data: {\"type\":\"done\",\"status\":\"completed\"}\n\n",
                        MediaType.TEXT_EVENT_STREAM));

        ChatResumeRequestDTO resume = new ChatResumeRequestDTO();
        resume.setConversationId("c-1");
        resume.setInterruptId("i-1");
        resume.setApproved(true);
        client.resumeStream(resume, "write-token", event -> { });
        server.verify();
    }

    @Test
    void legacyJavaChatUsesV1ContractAndDelegationToken() {
        server.expect(once(), requestTo("http://localhost:8000/v1/chat"))
                .andExpect(header("X-Api-Key", "internal"))
                .andExpect(header("X-Delegated-Token", "read-token"))
                .andRespond(withSuccess(
                        "{\"reply\":\"你好\",\"status\":\"completed\","
                                + "\"conversationId\":\"c-1\",\"intent\":\"chat\"}",
                        MediaType.APPLICATION_JSON));

        JavaAiClient legacyClient = new JavaAiClient(client);
        JavaChatRequestDTO request = new JavaChatRequestDTO();
        request.setContent("你好");
        request.setSessionId("c-1");
        request.setUserId("1");

        var response = legacyClient.chat(request, "read-token");

        assertEquals("你好", response.getFinalOutput());
        assertEquals("c-1", response.getSessionId());
        server.verify();
    }
}
