package com.wenrun.ai.knowledge.client;

import com.wenrun.ai.config.AiServiceProperties;
import com.wenrun.ai.knowledge.entity.AiKnowledgeDocument;
import com.wenrun.ai.knowledge.model.KnowledgeBaseType;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestClient;

import java.nio.file.Files;
import java.nio.file.Path;

import static org.hamcrest.Matchers.containsString;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.springframework.test.web.client.ExpectedCount.once;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.content;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.header;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.method;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withResourceNotFound;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withSuccess;

class KnowledgeAiClientTest {

    @TempDir
    Path tempDir;

    private MockRestServiceServer server;
    private KnowledgeAiClient client;

    @BeforeEach
    void setUp() {
        RestClient.Builder builder = RestClient.builder().baseUrl("http://localhost:8000");
        server = MockRestServiceServer.bindTo(builder).build();
        AiServiceProperties properties = new AiServiceProperties();
        properties.setApiKey("internal-secret");
        client = new KnowledgeAiClient(builder.build(), properties);
    }

    @Test
    void sendsScopedMultipartIngestRequest() throws Exception {
        Path source = tempDir.resolve("guide.md");
        Files.writeString(source, "hospital guide");
        AiKnowledgeDocument document = document(KnowledgeBaseType.HOSPITAL_CUSTOM);

        server.expect(once(), requestTo("http://localhost:8000/v1/knowledge/ingest"))
                .andExpect(method(HttpMethod.POST))
                .andExpect(header("X-Api-Key", "internal-secret"))
                .andExpect(content().string(containsString("documentId")))
                .andExpect(content().string(containsString("doc-1")))
                .andExpect(content().string(containsString("hospital-custom")))
                .andRespond(withSuccess(
                        "{\"status\":\"ready\",\"documentId\":\"doc-1\","
                                + "\"knowledgeBase\":\"hospital-custom\",\"chunkCount\":3}",
                        MediaType.APPLICATION_JSON));

        KnowledgeAiClient.IngestResult result = client.ingest(document, source);

        assertEquals(3, result.chunkCount());
        server.verify();
    }

    @Test
    void treatsMissingVectorsAsSuccessfulIdempotentDelete() {
        server.expect(requestTo(
                        "http://localhost:8000/v1/knowledge/hospital-custom/doc-1"))
                .andExpect(method(HttpMethod.DELETE))
                .andExpect(header("X-Api-Key", "internal-secret"))
                .andRespond(withResourceNotFound());

        client.delete(KnowledgeBaseType.HOSPITAL_CUSTOM, "doc-1");

        server.verify();
    }

    private static AiKnowledgeDocument document(KnowledgeBaseType knowledgeBase) {
        AiKnowledgeDocument document = new AiKnowledgeDocument();
        document.setDocumentId("doc-1");
        document.setKnowledgeBase(knowledgeBase);
        document.setOriginalName("guide.md");
        document.setContentType("text/markdown");
        return document;
    }
}
