package com.wenrun.ai.knowledge.service;

import com.wenrun.ai.knowledge.config.KnowledgeTaskProperties;
import com.wenrun.ai.knowledge.entity.AiKnowledgeDocument;
import com.wenrun.repository.AiKnowledgeDocumentRepository;
import com.wenrun.ai.knowledge.model.KnowledgeBaseType;
import com.wenrun.ai.knowledge.model.KnowledgeDocumentStatus;
import com.wenrun.ai.knowledge.vo.KnowledgeDocumentVO;
import com.wenrun.ai.knowledge.vo.KnowledgeUploadVO;
import com.wenrun.common.PageResult;
import com.wenrun.common.ResultCode;
import com.wenrun.common.exception.BusinessException;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.dao.DataAccessException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;
import org.springframework.util.StringUtils;
import org.springframework.web.multipart.MultipartFile;

import java.time.LocalDateTime;
import java.util.List;
import java.util.UUID;

@Slf4j
@Service
@RequiredArgsConstructor
public class KnowledgeDocumentServiceImpl implements KnowledgeDocumentService {

    private final AiKnowledgeDocumentRepository mapper;
    private final KnowledgeFileStorage storage;
    private final KnowledgeTaskService taskService;
    private final KnowledgeTaskProperties taskProperties;

    @Override
    @Transactional
    public KnowledgeUploadVO upload(
            KnowledgeBaseType knowledgeBase,
            MultipartFile file,
            Long uploadedBy) {
        if (uploadedBy == null) {
            throw new BusinessException(ResultCode.UNAUTHORIZED, "未登录或登录状态已失效");
        }

        KnowledgeFileStorage.StoredKnowledgeFile stored = storage.store(knowledgeBase, file);
        if (mapper.countActiveByDigest(knowledgeBase, stored.sha256()) > 0) {
            storage.delete(stored.relativePath().toString());
            throw new BusinessException("该知识库中已存在相同文件");
        }

        AiKnowledgeDocument document = buildDocument(knowledgeBase, file, stored, uploadedBy);
        try {
            mapper.insert(document);
        } catch (RuntimeException ex) {
            storage.delete(stored.relativePath().toString());
            throw ex;
        }

        afterCommit(() -> taskService.ingest(document.getDocumentId(), knowledgeBase));
        return new KnowledgeUploadVO(
                document.getDocumentId(), knowledgeBase.getPathValue(), document.getStatus());
    }

    @Override
    public PageResult<KnowledgeDocumentVO> list(
            KnowledgeBaseType knowledgeBase,
            KnowledgeDocumentStatus status,
            int pageNum,
            int pageSize) {
        if (pageNum < 1 || pageSize < 1 || pageSize > 100) {
            throw new BusinessException("分页参数无效");
        }
        int offset = (pageNum - 1) * pageSize;
        long total = mapper.countByFilter(knowledgeBase, status);
        List<KnowledgeDocumentVO> records = mapper.selectPageByFilter(
                        knowledgeBase, status, offset, pageSize)
                .stream()
                .map(KnowledgeDocumentServiceImpl::toVO)
                .toList();
        return PageResult.of(total, records);
    }

    @Override
    public KnowledgeDocumentVO get(KnowledgeBaseType knowledgeBase, String documentId) {
        return toVO(requireDocument(knowledgeBase, documentId));
    }

    @Override
    @Transactional
    public void retry(KnowledgeBaseType knowledgeBase, String documentId) {
        AiKnowledgeDocument document = requireDocument(knowledgeBase, documentId);
        if (document.getStatus() == KnowledgeDocumentStatus.FAILED) {
            updateStatus(document, KnowledgeDocumentStatus.PROCESSING);
            afterCommit(() -> taskService.ingest(documentId, knowledgeBase));
            return;
        }
        if (document.getStatus() == KnowledgeDocumentStatus.DELETE_FAILED) {
            updateStatus(document, KnowledgeDocumentStatus.DELETING);
            afterCommit(() -> taskService.delete(documentId, knowledgeBase));
            return;
        }
        throw new BusinessException("当前文档状态不允许重试");
    }

    @Override
    @Transactional
    public void delete(KnowledgeBaseType knowledgeBase, String documentId) {
        AiKnowledgeDocument document = requireDocument(knowledgeBase, documentId);
        if (document.getStatus() != KnowledgeDocumentStatus.READY
                && document.getStatus() != KnowledgeDocumentStatus.FAILED) {
            throw new BusinessException("当前文档状态不允许删除");
        }
        updateStatus(document, KnowledgeDocumentStatus.DELETING);
        afterCommit(() -> taskService.delete(documentId, knowledgeBase));
    }

    @EventListener(ApplicationReadyEvent.class)
    public void recoverStaleProcessing() {
        LocalDateTime before = LocalDateTime.now().minus(taskProperties.getStaleAfter());
        try {
            for (AiKnowledgeDocument document : mapper.selectStaleProcessing(before)) {
                mapper.updateStatus(
                        document.getDocumentId(),
                        document.getKnowledgeBase(),
                        KnowledgeDocumentStatus.FAILED,
                        0,
                        "服务重启或任务超时，请重新入库",
                        null,
                        null);
                log.warn("已恢复中断的知识库任务 | documentId={}", document.getDocumentId());
            }
        } catch (DataAccessException ex) {
            log.warn("跳过知识库任务恢复：请先执行知识库数据库迁移");
        }
    }

    private AiKnowledgeDocument requireDocument(KnowledgeBaseType knowledgeBase, String documentId) {
        AiKnowledgeDocument document = mapper.selectByDocumentIdAndKnowledgeBase(documentId, knowledgeBase);
        if (document == null) {
            throw new BusinessException(ResultCode.NOT_FOUND, "知识库文档不存在");
        }
        return document;
    }

    private void updateStatus(AiKnowledgeDocument document, KnowledgeDocumentStatus status) {
        mapper.updateStatus(
                document.getDocumentId(), document.getKnowledgeBase(), status,
                0, null, null, null);
    }

    private static AiKnowledgeDocument buildDocument(
            KnowledgeBaseType knowledgeBase,
            MultipartFile file,
            KnowledgeFileStorage.StoredKnowledgeFile stored,
            Long uploadedBy) {
        LocalDateTime now = LocalDateTime.now();
        AiKnowledgeDocument document = new AiKnowledgeDocument();
        document.setDocumentId(UUID.randomUUID().toString());
        document.setKnowledgeBase(knowledgeBase);
        document.setOriginalName(displayName(file.getOriginalFilename()));
        document.setStoragePath(stored.relativePath().toString());
        document.setContentType(file.getContentType());
        document.setFileSize(file.getSize());
        document.setFileSha256(stored.sha256());
        document.setStatus(KnowledgeDocumentStatus.PROCESSING);
        document.setChunkCount(0);
        document.setUploadedBy(uploadedBy);
        document.setCreatedAt(now);
        document.setUpdatedAt(now);
        return document;
    }

    private static String displayName(String originalName) {
        if (!StringUtils.hasText(originalName)) {
            return "unnamed";
        }
        String normalized = originalName.replace('\\', '/');
        return normalized.substring(normalized.lastIndexOf('/') + 1);
    }

    private static KnowledgeDocumentVO toVO(AiKnowledgeDocument document) {
        KnowledgeDocumentVO vo = new KnowledgeDocumentVO();
        vo.setDocumentId(document.getDocumentId());
        vo.setKnowledgeBase(document.getKnowledgeBase().getPathValue());
        vo.setOriginalName(document.getOriginalName());
        vo.setContentType(document.getContentType());
        vo.setFileSize(document.getFileSize());
        vo.setStatus(document.getStatus());
        vo.setChunkCount(document.getChunkCount());
        vo.setErrorMessage(document.getErrorMessage());
        vo.setUploadedBy(document.getUploadedBy());
        vo.setCreatedAt(document.getCreatedAt());
        vo.setUpdatedAt(document.getUpdatedAt());
        vo.setCompletedAt(document.getCompletedAt());
        return vo;
    }

    private static void afterCommit(Runnable task) {
        if (!TransactionSynchronizationManager.isActualTransactionActive()) {
            task.run();
            return;
        }
        TransactionSynchronizationManager.registerSynchronization(new TransactionSynchronization() {
            @Override
            public void afterCommit() {
                task.run();
            }
        });
    }
}
