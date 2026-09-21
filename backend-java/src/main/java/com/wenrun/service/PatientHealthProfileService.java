package com.wenrun.service;

import com.wenrun.dto.HealthProfileDTO;
import com.wenrun.vo.HealthProfileVO;
import com.wenrun.vo.HealthSnapshotVO;

import java.util.List;

/**
 * 患者健康档案
 */
public interface PatientHealthProfileService {

    HealthProfileVO get(Long patientId);

    HealthProfileVO create(Long patientId, HealthProfileDTO dto);

    HealthProfileVO update(Long patientId, HealthProfileDTO dto);

    void delete(Long patientId);

    List<HealthSnapshotVO> listSnapshots(Long patientId);

    void deleteSnapshot(Long patientId, Long snapshotId);
}
