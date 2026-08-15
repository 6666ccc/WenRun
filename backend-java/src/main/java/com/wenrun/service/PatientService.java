package com.wenrun.service;

import com.wenrun.dto.PatientQueryDTO;
import com.wenrun.entity.Patient;
import com.wenrun.vo.PatientVO;

import java.util.List;

/**
 * 患者业务接口
 */
public interface PatientService {

    List<PatientVO> list(PatientQueryDTO query);

    PatientVO getById(Long id);

    Long create(Patient patient);

    void update(Patient patient);
}
