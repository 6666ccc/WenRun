package com.wenrun.service.impl;

import com.wenrun.common.ResultCode;
import com.wenrun.common.constant.AccountType;
import com.wenrun.common.constant.BizStatus;
import com.wenrun.common.context.UserContext;
import com.wenrun.common.exception.BusinessException;
import com.wenrun.entity.Patient;
import com.wenrun.entity.UserPatientRelation;
import com.wenrun.enums.RelationType;
import com.wenrun.repository.PatientRepository;
import com.wenrun.repository.UserPatientRelationRepository;
import com.wenrun.service.PatientAccessService;
import com.wenrun.vo.AccessiblePatientVO;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.util.List;

/**
 * 患者授权只查 user_patient_relation。
 * patient.user_id 仅表示主账号/创建账号，不能单独作为访问依据。
 */
@Service
@RequiredArgsConstructor
public class PatientAccessServiceImpl implements PatientAccessService {

    private final UserPatientRelationRepository relationMapper;
    private final PatientRepository patientMapper;

    @Override
    public boolean hasAccess(Long patientId) {
        if (patientId == null || currentUserId() == null) {
            return false;
        }
        Patient patient = patientMapper.selectById(patientId);
        if (patient == null) {
            return false;
        }
        return isClinicalAccount() || relationMapper.selectActive(currentUserId(), patientId) != null;
    }

    @Override
    public void assertAccess(Long patientId) {
        requireAccessible(patientId);
    }

    @Override
    public Patient requireAccessible(Long patientId) {
        if (patientId == null) {
            throw new BusinessException("患者不存在");
        }
        Patient patient = patientMapper.selectById(patientId);
        if (patient == null) {
            throw new BusinessException("患者不存在");
        }
        if (isClinicalAccount()) {
            return patient;
        }
        Long userId = requireUserId();
        if (relationMapper.selectActive(userId, patientId) == null) {
            throw new BusinessException(ResultCode.FORBIDDEN, "无权访问该患者");
        }
        return patient;
    }

    @Override
    public Long resolvePatientId(Long requestedPatientId) {
        if (requestedPatientId != null) {
            requireAccessible(requestedPatientId);
            return requestedPatientId;
        }
        if (isClinicalAccount()) {
            throw new BusinessException("请指定患者");
        }
        Long userId = requireUserId();
        Long defaultPatientId = defaultPatientId(userId);
        if (defaultPatientId == null) {
            throw new BusinessException("患者档案不存在");
        }
        return requireAccessible(defaultPatientId).getId();
    }

    @Override
    public Long defaultPatientId(Long userId) {
        if (userId == null) {
            return null;
        }
        List<AccessiblePatientVO> patients = listAccessible(userId);
        return patients.stream()
                .filter(item -> Boolean.TRUE.equals(item.getIsDefault()))
                .map(AccessiblePatientVO::getPatientId)
                .findFirst()
                .orElseGet(() -> patients.isEmpty() ? null : patients.get(0).getPatientId());
    }

    @Override
    public List<AccessiblePatientVO> listAccessible(Long userId) {
        if (userId == null) {
            return List.of();
        }
        return relationMapper.selectAccessibleByUserId(userId);
    }

    @Override
    public void bindSelf(Long userId, Long patientId) {
        if (userId == null || patientId == null) {
            throw new BusinessException("账号与患者不能为空");
        }
        if (relationMapper.selectByUserIdAndPatientId(userId, patientId) != null) {
            return;
        }
        UserPatientRelation relation = new UserPatientRelation();
        relation.setUserId(userId);
        relation.setPatientId(patientId);
        relation.setRelationType(RelationType.SELF.getCode());
        relation.setIsDefault(relationMapper.countActiveByUserId(userId) == 0 ? 1 : 0);
        relation.setStatus(BizStatus.ENABLED);
        relationMapper.insert(relation);
    }

    private boolean isClinicalAccount() {
        String accountType = UserContext.getAccountType();
        return AccountType.STAFF.equals(accountType) || AccountType.INTERNAL.equals(accountType);
    }

    private Long currentUserId() {
        return UserContext.getUserId();
    }

    private Long requireUserId() {
        Long userId = currentUserId();
        if (userId == null) {
            throw new BusinessException(ResultCode.UNAUTHORIZED, "未登录或 Token 无效");
        }
        return userId;
    }
}
