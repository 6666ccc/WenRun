package com.wenrun.service.impl;

import com.wenrun.common.constant.AccountType;
import com.wenrun.common.context.UserContext;
import com.wenrun.common.exception.BusinessException;
import com.wenrun.util.BizNoUtil;
import com.wenrun.dto.PatientQueryDTO;
import com.wenrun.entity.Patient;
import com.wenrun.repository.PatientRepository;
import com.wenrun.service.PatientAccessService;
import com.wenrun.service.PatientService;
import com.wenrun.vo.AccessiblePatientVO;
import com.wenrun.vo.PatientVO;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.BeanUtils;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import java.util.List;

/**
 * 患者档案服务实现
 */
@Service
@RequiredArgsConstructor
public class PatientServiceImpl implements PatientService {

    private final PatientRepository patientMapper;
    private final PatientAccessService patientAccess;

    /** 按条件查询患者列表 */
    @Override
    public List<PatientVO> list(PatientQueryDTO query) {
        if (isPatientAccount()) {
            return patientAccess.listAccessible(UserContext.getUserId()).stream()
                    .map(this::toVo)
                    .toList();
        }
        return patientMapper.selectByCondition(query).stream()
                .map(this::toVo)
                .toList();
    }

    /** 根据 ID 查询患者详情 */
    @Override
    public PatientVO getById(Long id) {
        return toVo(patientAccess.requireAccessible(id));
    }

    /** 新建患者档案，未指定编号时自动生成 */
    @Override
    @Transactional
    public Long create(Patient patient) {
        if (!StringUtils.hasText(patient.getPatientNo())) {
            patient.setPatientNo(BizNoUtil.next("P"));
        }
        patientMapper.insert(patient);
        if (patient.getUserId() != null && patient.getId() != null) {
            patientAccess.bindSelf(patient.getUserId(), patient.getId());
        }
        return patient.getId();
    }

    /** 更新患者档案 */
    @Override
    public void update(Patient patient) {
        if (patient.getId() == null) {
            throw new BusinessException("患者ID不能为空");
        }
        patientAccess.assertAccess(patient.getId());
        patientMapper.updateById(patient);
    }

    private boolean isPatientAccount() {
        return AccountType.PATIENT.equals(UserContext.getAccountType());
    }

    private PatientVO toVo(Patient patient) {
        PatientVO vo = new PatientVO();
        BeanUtils.copyProperties(patient, vo);
        return vo;
    }

    private PatientVO toVo(AccessiblePatientVO accessible) {
        Patient patient = patientMapper.selectById(accessible.getPatientId());
        if (patient == null) {
            PatientVO vo = new PatientVO();
            vo.setId(accessible.getPatientId());
            vo.setPatientNo(accessible.getPatientNo());
            vo.setName(accessible.getName());
            return vo;
        }
        return toVo(patient);
    }
}
