package com.wenrun.ai.knowledge.controller;

import com.wenrun.ai.knowledge.model.KnowledgeBaseType;
import com.wenrun.ai.knowledge.model.KnowledgeDocumentStatus;
import com.wenrun.ai.knowledge.service.KnowledgeAdminGuard;
import com.wenrun.ai.knowledge.service.KnowledgeDocumentService;
import com.wenrun.ai.knowledge.vo.KnowledgeDocumentVO;
import com.wenrun.ai.knowledge.vo.KnowledgeUploadVO;
import com.wenrun.common.PageResult;
import com.wenrun.common.Result;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RequestPart;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

@RestController
@RequiredArgsConstructor
@RequestMapping("/api/ai/knowledge-bases/{knowledgeBase}/documents")
public class KnowledgeDocumentController {

    private final KnowledgeDocumentService service;
    private final KnowledgeAdminGuard adminGuard;

    @PostMapping
    public Result<KnowledgeUploadVO> upload(
            @PathVariable String knowledgeBase,
            @RequestPart("file") MultipartFile file) {
        adminGuard.requireAdmin();
        KnowledgeBaseType type = KnowledgeBaseType.fromPath(knowledgeBase);
        return Result.success(service.upload(type, file, adminGuard.currentUserId()));
    }

    @GetMapping
    public Result<PageResult<KnowledgeDocumentVO>> list(
            @PathVariable String knowledgeBase,
            @RequestParam(required = false) KnowledgeDocumentStatus status,
            @RequestParam(defaultValue = "1") int pageNum,
            @RequestParam(defaultValue = "20") int pageSize) {
        adminGuard.requireAdmin();
        KnowledgeBaseType type = KnowledgeBaseType.fromPath(knowledgeBase);
        return Result.success(service.list(type, status, pageNum, pageSize));
    }

    @GetMapping("/{documentId}")
    public Result<KnowledgeDocumentVO> get(
            @PathVariable String knowledgeBase,
            @PathVariable String documentId) {
        adminGuard.requireAdmin();
        return Result.success(service.get(KnowledgeBaseType.fromPath(knowledgeBase), documentId));
    }

    @PostMapping("/{documentId}/retry")
    public Result<Void> retry(
            @PathVariable String knowledgeBase,
            @PathVariable String documentId) {
        adminGuard.requireAdmin();
        service.retry(KnowledgeBaseType.fromPath(knowledgeBase), documentId);
        return Result.success();
    }

    @DeleteMapping("/{documentId}")
    public Result<Void> delete(
            @PathVariable String knowledgeBase,
            @PathVariable String documentId) {
        adminGuard.requireAdmin();
        service.delete(KnowledgeBaseType.fromPath(knowledgeBase), documentId);
        return Result.success();
    }
}
