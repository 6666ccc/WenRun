package com.example.wenrun.ai.knowledge.client;

import com.example.wenrun.ai.config.AiServiceProperties;
import com.example.wenrun.ai.exception.AiServiceException;
import com.example.wenrun.ai.knowledge.entity.AiKnowledgeDocument;
import com.example.wenrun.ai.knowledge.model.KnowledgeBaseType;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.core.io.FileSystemResource;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.util.StringUtils;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;

import java.nio.file.Path;

@Component
public class KnowledgeAiClient {

    private final RestClient restClient;
    private final AiServiceProperties properties;

    public KnowledgeAiClient(
            @Qualifier("aiRestClient") RestClient restClient,
            AiServiceProperties properties) {
        this.restClient = restClient;
        this.properties = properties;
    }

    public IngestResult ingest(AiKnowledgeDocument document, Path source) {
        // 第 1 步：取出可能为 null 的字段，转成明确的非空值再放入 MultiValueMap
        // （Eclipse 空分析要求 add/header 的值为 @NonNull Object）
        String documentId = requireText(document.getDocumentId(), "documentId");
        String knowledgeBase = requireText(
                document.getKnowledgeBase().getPathValue(), "knowledgeBase");
        String originalName = requireText(document.getOriginalName(), "originalName");
        String apiKey = requireApiKey();

        MultiValueMap<String, Object> body = new LinkedMultiValueMap<>();
        body.add("file", new FileSystemResource(source));
        body.add("documentId", documentId);
        body.add("knowledgeBase", knowledgeBase);
        body.add("originalName", originalName);

        try {
            IngestResult result = restClient.post()
                    .uri(properties.getKnowledgeIngestPath())
                    .header("X-Api-Key", apiKey)
                    .contentType(MediaType.MULTIPART_FORM_DATA)
                    .body(body)
                    .retrieve()
                    .onStatus(status -> status.isError(), (request, response) -> {
                        throw new AiServiceException(
                                "AI 知识库入库失败: HTTP " + response.getStatusCode().value());
                    })
                    .body(IngestResult.class);
            if (result == null || result.chunkCount() < 1) {
                throw new AiServiceException("AI 知识库入库未返回有效切片");
            }
            return result;
        } catch (AiServiceException ex) {
            throw ex;
        } catch (RestClientException ex) {
            throw new AiServiceException("无法连接 AI 知识库服务", ex);
        }
    }

    public void delete(KnowledgeBaseType knowledgeBase, String documentId) {
        String apiKey = requireApiKey();
        try {
            restClient.delete()
                    .uri(properties.getKnowledgeDeletePath(), knowledgeBase.getPathValue(), documentId)
                    .header("X-Api-Key", apiKey)
                    .exchange((request, response) -> {
                        if (response.getStatusCode() == HttpStatus.NOT_FOUND) {
                            return null;
                        }
                        if (response.getStatusCode().isError()) {
                            throw new AiServiceException(
                                    "AI 知识库删除失败: HTTP " + response.getStatusCode().value());
                        }
                        return null;
                    });
        } catch (AiServiceException ex) {
            throw ex;
        } catch (RestClientException ex) {
            throw new AiServiceException("无法连接 AI 知识库服务", ex);
        }
    }

    /**
     * 读取并校验 ai.service.api-key，保证返回值非空，满足 header 的 @NonNull 约束。
     */
    private String requireApiKey() {
        String apiKey = properties.getApiKey();
        if (!StringUtils.hasText(apiKey)) {
            throw new AiServiceException("未配置 ai.service.api-key，无法调用 AI 知识库服务");
        }
        return apiKey;
    }

    /**
     * 将可空字符串校验为非空文本；为空时抛业务异常，避免写入 MultiValueMap 触发空安全告警。
     */
    private static String requireText(String value, String fieldName) {
        if (!StringUtils.hasText(value)) {
            throw new AiServiceException("知识库请求缺少必填字段: " + fieldName);
        }
        return value;
    }

    public record IngestResult(String documentId, String knowledgeBase, int chunkCount) {
    }
}
