package com.wenrun.ai.controller;

import com.wenrun.ai.security.KnowledgeAccessService;
import com.wenrun.ai.service.KnowledgeGatewayService;
import com.wenrun.common.Result;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.util.Map;

/** 登录用户访问院内知识库。身份和角色在 Java 侧确认，解析与发布由 Python 完成。 */
@RestController
@RequestMapping("/api/ai/knowledge")
@RequiredArgsConstructor
public class KnowledgeController {

    private final KnowledgeGatewayService gateway;
    private final KnowledgeAccessService access;

    @PostMapping(value = "/documents", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public Result<Map<String, Object>> submit(
            @RequestParam("file") MultipartFile file,
            @RequestParam(required = false) String documentId,
            @RequestParam(defaultValue = "public") String scope,
            @RequestParam(required = false) String effectiveFrom,
            @RequestParam(required = false) String expiresAt,
            @RequestParam(required = false) String metadata) throws IOException {
        return Result.success(gateway.submit(
                access.requireAdministrator(), file.getBytes(), filename(file),
                documentId, scope, effectiveFrom, expiresAt, metadata));
    }

    @PostMapping(value = "/documents/{documentId}/rebuild", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public Result<Map<String, Object>> rebuild(
            @PathVariable String documentId,
            @RequestParam("file") MultipartFile file,
            @RequestParam(defaultValue = "public") String scope,
            @RequestParam(required = false) String effectiveFrom,
            @RequestParam(required = false) String expiresAt,
            @RequestParam(required = false) String metadata) throws IOException {
        return Result.success(gateway.rebuild(
                access.requireAdministrator(), documentId, file.getBytes(), filename(file),
                scope, effectiveFrom, expiresAt, metadata));
    }

    @GetMapping("/documents")
    public Result<Map<String, Object>> list(
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "20") int pageSize,
            @RequestParam(required = false) String scope) {
        return Result.success(gateway.list(access.requireAdministrator(), page, pageSize, scope));
    }

    @GetMapping("/documents/{documentId}")
    public Result<Map<String, Object>> document(@PathVariable String documentId) {
        return Result.success(gateway.getDocument(access.requireAdministrator(), documentId));
    }

    @GetMapping("/jobs/{jobId}")
    public Result<Map<String, Object>> job(@PathVariable String jobId) {
        return Result.success(gateway.getJob(access.requireAdministrator(), jobId));
    }

    @PostMapping("/jobs/{jobId}/retry")
    public Result<Map<String, Object>> retry(@PathVariable String jobId) {
        return Result.success(gateway.retry(access.requireAdministrator(), jobId));
    }

    @PostMapping("/documents/{documentId}/versions/{version}/review")
    public Result<Map<String, Object>> review(
            @PathVariable String documentId,
            @PathVariable int version,
            @RequestParam String decision,
            @RequestParam(required = false) String reason) {
        return Result.success(gateway.review(
                access.requireAdministrator(), documentId, version, decision, reason));
    }

    @PostMapping("/documents/{documentId}/versions/{version}/publish")
    public Result<Map<String, Object>> publish(
            @PathVariable String documentId, @PathVariable int version) {
        return Result.success(gateway.publish(access.requireAdministrator(), documentId, version));
    }

    @GetMapping("/assets/{assetId}")
    public ResponseEntity<byte[]> asset(
            @PathVariable String assetId, @RequestParam(defaultValue = "public") String scope) {
        KnowledgeGatewayService.Asset file = gateway.readAsset(access.sourceAccess(scope), assetId, scope);
        return ResponseEntity.ok()
                .header(HttpHeaders.CONTENT_DISPOSITION, file.contentDisposition())
                .header("X-Content-Type-Options", "nosniff")
                .header("Cache-Control", "private, no-store")
                .contentType(mediaType(file.contentType()))
                .body(file.content());
    }

    private static String filename(MultipartFile file) {
        String name = file.getOriginalFilename();
        if (name == null || name.isBlank()) {
            throw new com.wenrun.common.exception.BusinessException("请上传带文件名的资料");
        }
        int slash = Math.max(name.lastIndexOf('/'), name.lastIndexOf('\\'));
        return slash >= 0 ? name.substring(slash + 1) : name;
    }

    private static MediaType mediaType(String value) {
        try {
            return MediaType.parseMediaType(value);
        } catch (Exception ex) {
            return MediaType.APPLICATION_OCTET_STREAM;
        }
    }
}
