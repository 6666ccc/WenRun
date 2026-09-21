package com.wenrun.service;

import com.wenrun.entity.Patient;
import com.wenrun.vo.AccessiblePatientVO;

import java.util.List;

/**
 * 统一的患者访问权限：Subject = patient_id，Actor = 登录 user_id。
 */
public interface PatientAccessService {

    boolean hasAccess(Long patientId);

    void assertAccess(Long patientId);

    Patient requireAccessible(Long patientId);

    Long resolvePatientId(Long requestedPatientId);

    Long defaultPatientId(Long userId);

    List<AccessiblePatientVO> listAccessible(Long userId);

    void bindSelf(Long userId, Long patientId);
}
