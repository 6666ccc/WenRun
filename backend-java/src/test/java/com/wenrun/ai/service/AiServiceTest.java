package com.wenrun.ai.service;

import com.wenrun.ai.vo.aiReply;
import com.wenrun.ai.vo.aiRequest;
import com.wenrun.common.ResultCode;
import com.wenrun.common.exception.BusinessException;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestClient;

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
    void forwardsChatRequestAndKeepsRagSources() {
        RestClient.Builder builder = RestClient.builder().baseUrl("http://python.test");
        MockRestServiceServer server = MockRestServiceServer.bindTo(builder).build();
        aiService service = new aiService(builder.build(), "service-key");
        server.expect(requestTo("http://python.test/v1/chat"))
                .andExpect(method(HttpMethod.POST))
                .andExpect(header("X-Api-Key", "service-key"))
                .andExpect(jsonPath("$.message").value("普通感冒有哪些症状？"))
                .andExpect(jsonPath("$.conversationId").value("conversation-1"))
                .andExpect(jsonPath("$.memoryEnabled").value(true))
                .andRespond(withSuccess("""
                        {
                          "reply": "根据院内资料整理的回复 [S1]",
                          "status": "completed",
                          "conversationId": "conversation-1",
                          "selectedAgents": ["knowledge", "chat"],
                          "sources": [
                            {
                              "id": "S1",
                              "document_id": "document-1",
                              "title": "感冒共识.pdf",
                              "page": 4
                            }
                          ]
                        }
                        """, MediaType.APPLICATION_JSON));

        aiRequest request = new aiRequest();
        request.setMessage("普通感冒有哪些症状？");
        request.setConversationId("conversation-1");
        request.setMemoryEnabled(Boolean.TRUE);

        aiReply reply = service.chat(request);

        assertEquals("根据院内资料整理的回复 [S1]", reply.getReply());
        assertEquals("completed", reply.getStatus());
        assertEquals("conversation-1", reply.getConversationId());
        assertEquals("knowledge", reply.getSelectedAgents().get(0));
        assertEquals("chat", reply.getSelectedAgents().get(1));
        assertEquals(1, reply.getSources().size());
        assertEquals("document-1", reply.getSources().get(0).getDocumentId());
        assertEquals(4, reply.getSources().get(0).getPage());
        server.verify();
    }

    @Test
    void convertsPythonHttpErrorsToServiceUnavailable() {
        RestClient.Builder builder = RestClient.builder().baseUrl("http://python.test");
        MockRestServiceServer server = MockRestServiceServer.bindTo(builder).build();
        aiService service = new aiService(builder.build(), "");
        server.expect(requestTo("http://python.test/v1/chat"))
                .andExpect(method(HttpMethod.POST))
                .andRespond(withServerError());

        aiRequest request = new aiRequest();
        request.setMessage("你好");

        BusinessException exception = assertThrows(BusinessException.class, () -> service.chat(request));

        assertEquals(ResultCode.SERVICE_UNAVAILABLE, exception.getCode());
        server.verify();
    }
}
