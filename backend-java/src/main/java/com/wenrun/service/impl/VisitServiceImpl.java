package com.wenrun.service.impl;

import com.wenrun.common.constant.BizStatus;
import com.wenrun.common.constant.AccountType;
import com.wenrun.common.context.UserContext;
import com.wenrun.common.exception.BusinessException;
import com.wenrun.util.BizNoUtil;
import com.wenrun.dto.VisitUpdateDTO;
import com.wenrun.entity.OutpatientVisit;
import com.wenrun.entity.Registration;
import com.wenrun.repository.OutpatientVisitRepository;
import com.wenrun.repository.RegistrationRepository;
import com.wenrun.repository.PatientRepository;
import com.wenrun.service.VisitService;
import com.wenrun.service.support.CurrentStaffSupport;
import com.wenrun.vo.VisitVO;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;

/**
 * 门诊就诊服务实现 — 接诊、病历填写与完诊
 */
@Service
@RequiredArgsConstructor
public class VisitServiceImpl implements VisitService {

    private final OutpatientVisitRepository visitMapper;
    private final RegistrationRepository registrationMapper;
    private final PatientRepository patientMapper;
    private final CurrentStaffSupport currentStaffSupport;

    /** 按状态与医生查询就诊记录列表 */
    @Override
    public List<VisitVO> list(Integer status, Long staffId) {
        return list(status, staffId, null);
    }

    @Override
    public List<VisitVO> list(Integer status, Long staffId, Long patientId) {
        if (AccountType.PATIENT.equals(UserContext.getAccountType())) {
            patientId = currentPatientId();
            staffId = null;
        }
        return visitMapper.selectList(status, staffId, patientId);
    }

    /** 查询就诊详情，校验当前医生权限 */
    @Override
    public VisitVO getById(Long id) {
        VisitVO vo = visitMapper.selectVoById(id);
        if (vo == null) {
            throw new BusinessException("就诊记录不存在");
        }
        assertPatientCanRead(vo.getPatientId());
        currentStaffSupport.assertOwnsStaff(vo.getStaffId());
        return vo;
    }

    private void assertPatientCanRead(Long patientId) {
        if (!AccountType.PATIENT.equals(UserContext.getAccountType())) {
            return;
        }
        if (!patientId.equals(currentPatientId())) {
            throw new BusinessException("无权查看该就诊记录");
        }
    }

    private Long currentPatientId() {
        var patient = patientMapper.selectByUserId(UserContext.getUserId());
        if (patient == null) {
            throw new BusinessException("患者档案不存在");
        }
        return patient.getId();
    }

    /** 根据挂号单开始接诊，创建就诊记录并更新挂号状态 */
    @Override
    @Transactional
    public Long startVisit(Long registrationId) {
        Registration reg = registrationMapper.selectById(registrationId);
        if (reg == null) {
            throw new BusinessException("挂号单不存在");
        }
        if (reg.getStatus() != BizStatus.REG_REGISTERED) {
            throw new BusinessException("挂号单状态不允许接诊");
        }
        currentStaffSupport.assertOwnsStaff(reg.getStaffId());
        OutpatientVisit existing = visitMapper.selectByRegistrationId(registrationId);
        if (existing != null) {
            return existing.getId();
        }
        OutpatientVisit visit = new OutpatientVisit();
        visit.setVisitNo(BizNoUtil.next("VIS"));
        visit.setRegistrationId(registrationId);
        visit.setPatientId(reg.getPatientId());
        visit.setStaffId(reg.getStaffId());
        visit.setVisitTime(LocalDateTime.now());
        visit.setStatus(BizStatus.VISIT_IN_PROGRESS);
        visitMapper.insert(visit);
        registrationMapper.updateStatus(registrationId, BizStatus.REG_VISITED);
        return visit.getId();
    }

    /** 更新主诉、诊断；complete=true 时标记为已完诊 */
    @Override
    public void updateVisit(Long id, VisitUpdateDTO dto) {
        OutpatientVisit visit = visitMapper.selectById(id);
        if (visit == null) {
            throw new BusinessException("就诊记录不存在");
        }
        currentStaffSupport.assertOwnsStaff(visit.getStaffId());
        if (dto.getChiefComplaint() != null) {
            visit.setChiefComplaint(dto.getChiefComplaint());
        }
        if (dto.getDiagnosis() != null) {
            visit.setDiagnosis(dto.getDiagnosis());
        }
        if (Boolean.TRUE.equals(dto.getComplete())) {
            visit.setStatus(BizStatus.VISIT_COMPLETED);
        }
        visitMapper.updateById(visit);
    }
}
