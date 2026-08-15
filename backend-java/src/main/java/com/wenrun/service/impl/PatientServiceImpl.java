package com.wenrun.service.impl;

import com.wenrun.common.constant.AccountType;
import com.wenrun.common.context.UserContext;
import com.wenrun.common.exception.BusinessException;
import com.wenrun.util.BizNoUtil;
import com.wenrun.dto.PatientQueryDTO;
import com.wenrun.entity.Patient;
import com.wenrun.repository.PatientRepository;
import com.wenrun.service.PatientService;
import com.wenrun.vo.PatientVO;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.BeanUtils;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import java.util.List;

/**
 * 患者档案服务实现
 */
@Service
@RequiredArgsConstructor
public class PatientServiceImpl implements PatientService {

    private final PatientRepository patientMapper;

    /** 按条件查询患者列表 */
    @Override
    public List<PatientVO> list(PatientQueryDTO query) {
        if (isPatientAccount()) {
            Patient patient = patientMapper.selectByUserId(UserContext.getUserId());
            return patient == null ? List.of() : List.of(toVo(patient));
        }
        return patientMapper.selectByCondition(query).stream()
                .map(this::toVo)
                .toList();
    }

    /** 根据 ID 查询患者详情 */
    @Override
    public PatientVO getById(Long id) {
        Patient patient = patientMapper.selectById(id);
        if (patient == null) {
            throw new BusinessException("患者不存在");
        }
        assertPatientOwnership(patient);
        return toVo(patient);
    }

    /** 新建患者档案，未指定编号时自动生成 */
    @Override
    public Long create(Patient patient) {
        if (!StringUtils.hasText(patient.getPatientNo())) {
            patient.setPatientNo(BizNoUtil.next("P"));
        }
        patientMapper.insert(patient);
        return patient.getId();
    }

    /** 更新患者档案 */
    @Override
    public void update(Patient patient) {
        if (patient.getId() == null) {
            throw new BusinessException("患者ID不能为空");
        }
        Patient existing = patientMapper.selectById(patient.getId());
        if (existing == null) {
            throw new BusinessException("患者不存在");
        }
        assertPatientOwnership(existing);
        patientMapper.updateById(patient);
    }

    private boolean isPatientAccount() {
        return AccountType.PATIENT.equals(UserContext.getAccountType());
    }

    private void assertPatientOwnership(Patient patient) {
        if (isPatientAccount() && !UserContext.getUserId().equals(patient.getUserId())) {
            throw new BusinessException("Access denied");
        }
    }

    private PatientVO toVo(Patient patient) {
        PatientVO vo = new PatientVO();
        BeanUtils.copyProperties(patient, vo);
        return vo;
    }
}
