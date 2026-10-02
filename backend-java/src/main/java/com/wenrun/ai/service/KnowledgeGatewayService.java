package com.wenrun.ai.service;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.wenrun.ai.security.KnowledgeAccessService;
import com.wenrun.common.ResultCode;
import com.wenrun.common.exception.BusinessException;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.http.ContentDisposition;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Service;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.util.StringUtils;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientResponseException;

import java.nio.charset.StandardCharsets;
import java.util.Map;
import java.util.function.Supplier;

/** Java 登录网关到 Python knowledge service 的代理。 */
@Service
public class KnowledgeGatewayService {

    private static final ParameterizedTypeReference<Map<String, Object>> MAP_TYPE =
            new ParameterizedTypeReference<>() { };
    private static final TypeReference<Map<String, Object>> JSON_MAP = new TypeReference<>() { };
    private static final java.util.Set<String> SAFE_INLINE_TYPES = java.util.Set.of(
            "application/pdf", "image/png", "image/jpeg", "text/plain");

    private final RestClient pythonClient;
    private final String apiKey;
    private final ObjectMapper objectMapper;

    @Autowired
    public KnowledgeGatewayService(
            RestClient.Builder builder,
            ObjectMapper objectMapper,
            @Value("${AI_SERVICE_BASE_URL:http://localhost:8000}") String baseUrl,
            @Value("${AI_SERVICE_API_KEY:}") String apiKey,
            @Value("${AI_SERVICE_CONNECT_TIMEOUT_MILLIS:5000}") int connectTimeoutMillis,
            @Value("${AI_SERVICE_READ_TIMEOUT_MILLIS:30000}") int readTimeoutMillis) {
        SimpleClientHttpRequestFactory requestFactory = new SimpleClientHttpRequestFactory();
        requestFactory.setConnectTimeout(Math.max(1, connectTimeoutMillis));
        requestFactory.setReadTimeout(Math.max(1, readTimeoutMillis));
        this.pythonClient = builder.baseUrl(baseUrl).requestFactory(requestFactory).build();
        this.apiKey = apiKey;
        this.objectMapper = objectMapper;
    }

    /** 仅供不访问真实网络的单元测试使用。 */
    KnowledgeGatewayService(RestClient pythonClient, String apiKey) {
        this.pythonClient = pythonClient;
        this.apiKey = apiKey;
        this.objectMapper = new ObjectMapper();
    }

    public Map<String, Object> submit(
            KnowledgeAccessService.AccessContext access,
            byte[] content,
            String filename,
            String documentId,
            String scope,
            String effectiveFrom,
            String expiresAt,
            String metadataJson) {
        return execute(() -> {
            MultiValueMap<String, Object> form = new LinkedMultiValueMap<>();
            form.add("file", new ByteArrayResource(content) {
                @Override
                public String getFilename() {
                    return filename;
                }
            });
            addIfPresent(form, "documentId", documentId);
            addIfPresent(form, "effectiveFrom", effectiveFrom);
            addIfPresent(form, "expiresAt", expiresAt);
            addIfPresent(form, "scope", scope);
            addIfPresent(form, "metadata", metadataJson);
            return authenticated(pythonClient.post().uri("/v1/knowledge/documents"), access)
                    .contentType(MediaType.MULTIPART_FORM_DATA)
                    .body(form)
                    .retrieve()
                    .body(MAP_TYPE);
        });
    }

    public Map<String, Object> rebuild(
            KnowledgeAccessService.AccessContext access,
            String documentId,
            byte[] content,
            String filename,
            String scope,
            String effectiveFrom,
            String expiresAt,
            String metadataJson) {
        return execute(() -> {
            MultiValueMap<String, Object> form = new LinkedMultiValueMap<>();
            form.add("file", new ByteArrayResource(content) {
                @Override
                public String getFilename() {
                    return filename;
                }
            });
            addIfPresent(form, "effectiveFrom", effectiveFrom);
            addIfPresent(form, "expiresAt", expiresAt);
            addIfPresent(form, "scope", scope);
            addIfPresent(form, "metadata", metadataJson);
            form.add("forceRebuild", "true");
            return authenticated(pythonClient.post()
                            .uri("/v1/knowledge/documents/{documentId}/rebuild", documentId), access)
                    .contentType(MediaType.MULTIPART_FORM_DATA)
                    .body(form)
                    .retrieve()
                    .body(MAP_TYPE);
        });
    }

    public Map<String, Object> list(
            KnowledgeAccessService.AccessContext access,
            int page,
            int pageSize,
            String scope) {
        return execute(() -> authenticated(pythonClient.get().uri(uriBuilder -> {
            var builder = uriBuilder.path("/v1/knowledge/documents")
                    .queryParam("page", page)
                    .queryParam("pageSize", pageSize);
            if (StringUtils.hasText(scope)) builder.queryParam("scope", scope);
            return builder.build();
        }), access).retrieve().body(MAP_TYPE));
    }

    public Map<String, Object> getDocument(
            KnowledgeAccessService.AccessContext access, String documentId) {
        return execute(() -> authenticated(pythonClient.get()
                .uri("/v1/knowledge/documents/{documentId}", documentId), access)
                .retrieve().body(MAP_TYPE));
    }

    public Map<String, Object> getJob(KnowledgeAccessService.AccessContext access, String jobId) {
        return execute(() -> authenticated(pythonClient.get()
                .uri("/v1/knowledge/jobs/{jobId}", jobId), access)
                .retrieve().body(MAP_TYPE));
    }

    public Map<String, Object> retry(KnowledgeAccessService.AccessContext access, String jobId) {
        return execute(() -> authenticated(pythonClient.post()
                .uri("/v1/knowledge/jobs/{jobId}/retry", jobId), access)
                .retrieve().body(MAP_TYPE));
    }

    public Map<String, Object> review(
            KnowledgeAccessService.AccessContext access,
            String documentId,
            int version,
            String decision,
            String reason) {
        return execute(() -> {
            MultiValueMap<String, Object> form = new LinkedMultiValueMap<>();
            form.add("decision", decision);
            addIfPresent(form, "reason", reason);
            return authenticated(pythonClient.post().uri(
                            "/v1/knowledge/documents/{documentId}/versions/{version}/review",
                            documentId, version), access)
                    .contentType(MediaType.APPLICATION_FORM_URLENCODED)
                    .body(form)
                    .retrieve().body(MAP_TYPE);
        });
    }

    public Map<String, Object> publish(
            KnowledgeAccessService.AccessContext access, String documentId, int version) {
        return execute(() -> authenticated(pythonClient.post().uri(
                        "/v1/knowledge/documents/{documentId}/versions/{version}/publish",
                        documentId, version), access)
                .retrieve().body(MAP_TYPE));
    }

    public Asset readAsset(
            KnowledgeAccessService.AccessContext access, String assetId, String scope) {
        return execute(() -> {
            ResponseEntity<byte[]> response = authenticated(pythonClient.get().uri(uriBuilder -> uriBuilder
                            .path("/v1/knowledge/assets/{assetId}")
                            .queryParam("scope", scope)
                            .build(assetId)), access)
                    .retrieve().toEntity(byte[].class);
            byte[] body = response.getBody() == null ? new byte[0] : response.getBody();
            String contentType = response.getHeaders().getContentType() == null
                    ? MediaType.APPLICATION_OCTET_STREAM_VALUE
                    : response.getHeaders().getContentType().toString();
            String filename = response.getHeaders().getContentDisposition().getFilename();
            if (!StringUtils.hasText(filename)) filename = "knowledge-source";
            return new Asset(body, filename, contentType);
        });
    }

    private <S extends RestClient.RequestHeadersSpec<S>> S authenticated(
            S request,
            KnowledgeAccessService.AccessContext access) {
        request.headers(headers -> {
            if (StringUtils.hasText(apiKey)) headers.set("X-Api-Key", apiKey);
            headers.set("X-Delegated-Token", access.delegatedToken());
        });
        return request;
    }

    private void addIfPresent(MultiValueMap<String, Object> map, String key, String value) {
        if (StringUtils.hasText(value)) map.add(key, value);
    }

    private <T> T execute(Supplier<T> action) {
        try {
            return action.get();
        } catch (RestClientResponseException ex) {
            throw toBusinessException(ex);
        } catch (BusinessException ex) {
            throw ex;
        } catch (Exception ex) {
            BusinessException failure = new BusinessException(
                    ResultCode.SERVICE_UNAVAILABLE, "知识库服务暂不可用，请稍后重试");
            failure.initCause(ex);
            throw failure;
        }
    }

    private BusinessException toBusinessException(RestClientResponseException ex) {
        int upstreamStatus = ex.getStatusCode().value();
        String message = "知识库服务暂不可用，请稍后重试";
        try {
            Map<String, Object> body = objectMapper.readValue(
                    ex.getResponseBodyAsString(StandardCharsets.UTF_8), JSON_MAP);
            Object detail = body.get("detail");
            if (detail == null) detail = body.get("message");
            if (detail != null && !String.valueOf(detail).isBlank()) message = String.valueOf(detail);
        } catch (Exception ignored) {
            // 不把上游异常正文或路径暴露给浏览器。
        }
        int code = switch (upstreamStatus) {
            case 400, 413, 422 -> ResultCode.BAD_REQUEST;
            case 401 -> ResultCode.SERVICE_UNAVAILABLE;
            case 403 -> ResultCode.FORBIDDEN;
            case 404 -> ResultCode.NOT_FOUND;
            case 409 -> ResultCode.CONFLICT;
            default -> ResultCode.SERVICE_UNAVAILABLE;
        };
        if (upstreamStatus == 409) message = "资料状态已变化，请刷新后重试";
        BusinessException failure = new BusinessException(code, message);
        failure.initCause(ex);
        return failure;
    }

    public record Asset(byte[] content, String filename, String contentType) {
        public boolean isSafeInline() {
            String baseType = contentType.split(";", 2)[0].trim().toLowerCase();
            return SAFE_INLINE_TYPES.contains(baseType);
        }

        public String contentDisposition() {
            ContentDisposition disposition = ContentDisposition.builder(isSafeInline() ? "inline" : "attachment")
                    .filename(filename, StandardCharsets.UTF_8)
                    .build();
            return disposition.toString();
        }
    }
}
