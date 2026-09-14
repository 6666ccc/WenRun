package com.wenrun.ai.service;

import com.wenrun.ai.vo.AiMemoryWriteRequest;
import com.wenrun.common.ResultCode;
import com.wenrun.common.exception.BusinessException;
import com.wenrun.entity.AiPatientMemory;
import com.wenrun.repository.AiPatientMemoryRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Set;
import java.util.UUID;
import java.util.regex.Pattern;

@Service
@RequiredArgsConstructor
public class AiPatientMemoryService {
    public static final Set<String> ALLOWED_TYPES = Set.of(
            "communication_preference", "appointment_preference", "accessibility_need");
    private static final Pattern FORBIDDEN_CLINICAL_FACT = Pattern.compile(
            "(?i)(症状|诊断|确诊|处方|检验|化验|检查结果|过敏|药物|服药|服用|用药|剂量"
                    + "|胸痛|腹痛|头痛|发热|发烧|咳嗽|呼吸困难|出血|呕吐|腹泻|头晕"
                    + "|高血压|糖尿病)|\\d+(?:\\.\\d+)?\\s*(mg|毫克|ml|毫升)"
    );

    private final AiPatientMemoryRepository repository;

    public List<AiPatientMemory> listActive(Long patientId, int limit) {
        requirePatient(patientId);
        return repository.selectActiveByPatientId(patientId, Math.max(1, Math.min(limit, 20)));
    }

    public List<AiPatientMemory> listManageable(Long patientId, int page, int size) {
        requirePatient(patientId);
        int boundedSize = Math.max(1, Math.min(size, 50));
        int offset = Math.max(0, page) * boundedSize;
        return repository.selectLatestByPatientId(patientId, offset, boundedSize);
    }

    @Transactional
    public AiPatientMemory createConfirmed(Long patientId, AiMemoryWriteRequest request) {
        validate(patientId, request);
        AiPatientMemory memory = new AiPatientMemory();
        memory.setMemoryId(UUID.randomUUID().toString());
        memory.setPatientId(patientId);
        memory.setType(request.getType());
        memory.setContent(request.getContent().trim());
        memory.setSourceConversationId(request.getSourceConversationId().trim());
        memory.setSourceMessageId(request.getSourceMessageId());
        memory.setStatus("active");
        memory.setVersion(1);
        memory.setConfidence(BigDecimal.ONE);
        memory.setExpireTime(request.getExpireTime());
        repository.insert(memory);
        return memory;
    }

    @Transactional
    public AiPatientMemory update(Long patientId, String memoryId, AiMemoryWriteRequest request) {
        AiPatientMemory current = requireCurrent(patientId, memoryId);
        if (request != null) {
            // Browser edits may change the preference, but cannot rewrite the
            // original audited provenance to an arbitrary conversation/message.
            request.setSourceConversationId(current.getSourceConversationId());
            request.setSourceMessageId(current.getSourceMessageId());
        }
        validate(patientId, request);
        if (request.getExpectedVersion() == null
                || !request.getExpectedVersion().equals(current.getVersion())) {
            throw new BusinessException(409, "记忆已被更新，请刷新后重试");
        }
        repository.markSuperseded(patientId, memoryId, current.getVersion());
        AiPatientMemory next = new AiPatientMemory();
        next.setMemoryId(memoryId);
        next.setPatientId(patientId);
        next.setType(request.getType());
        next.setContent(request.getContent().trim());
        next.setSourceConversationId(request.getSourceConversationId().trim());
        next.setSourceMessageId(request.getSourceMessageId());
        next.setStatus("active");
        next.setVersion(current.getVersion() + 1);
        next.setConfidence(BigDecimal.ONE);
        next.setExpireTime(request.getExpireTime());
        repository.insert(next);
        return next;
    }

    @Transactional
    public void confirm(Long patientId, String memoryId) {
        AiPatientMemory current = requireCurrent(patientId, memoryId);
        if (!"pending".equals(current.getStatus())) {
            throw new BusinessException(ResultCode.BAD_REQUEST, "该记忆不处于待确认状态");
        }
        repository.activatePending(patientId, memoryId, current.getVersion());
    }

    @Transactional
    public void delete(Long patientId, String memoryId) {
        requirePatient(patientId);
        repository.softDeleteCurrent(patientId, memoryId);
    }

    private AiPatientMemory requireCurrent(Long patientId, String memoryId) {
        requirePatient(patientId);
        AiPatientMemory current = repository.selectLatestForUpdate(patientId, memoryId);
        if (current == null || "deleted".equals(current.getStatus())) {
            throw new BusinessException(ResultCode.NOT_FOUND, "记忆不存在");
        }
        return current;
    }

    private void validate(Long patientId, AiMemoryWriteRequest request) {
        requirePatient(patientId);
        if (request == null || !ALLOWED_TYPES.contains(request.getType())) {
            throw new BusinessException(ResultCode.BAD_REQUEST, "不支持的记忆类型");
        }
        if (!StringUtils.hasText(request.getContent()) || request.getContent().trim().length() > 500) {
            throw new BusinessException(ResultCode.BAD_REQUEST, "记忆内容不能为空且不能超过500字");
        }
        if (FORBIDDEN_CLINICAL_FACT.matcher(request.getContent()).find()) {
            throw new BusinessException(ResultCode.BAD_REQUEST, "症状、诊断、药物剂量等不能保存为长期偏好");
        }
        if (!StringUtils.hasText(request.getSourceConversationId())) {
            throw new BusinessException(ResultCode.BAD_REQUEST, "记忆必须包含来源会话");
        }
        if (request.getSourceMessageId() == null) {
            throw new BusinessException(ResultCode.BAD_REQUEST, "记忆必须关联来源消息");
        }
        if (request.getExpireTime() != null && !request.getExpireTime().isAfter(LocalDateTime.now())) {
            throw new BusinessException(ResultCode.BAD_REQUEST, "记忆过期时间必须晚于当前时间");
        }
    }

    private void requirePatient(Long patientId) {
        if (patientId == null) {
            throw new BusinessException(ResultCode.FORBIDDEN, "当前账号还没有绑定患者档案");
        }
    }
}
