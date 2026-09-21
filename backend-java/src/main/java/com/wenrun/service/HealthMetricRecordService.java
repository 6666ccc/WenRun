package com.wenrun.service;

import com.wenrun.dto.HealthMetricRecordDTO;
import com.wenrun.vo.HealthMetricRecordVO;
import com.wenrun.vo.HealthMetricTrendVO;
import com.wenrun.vo.HealthMetricTypeVO;

import java.util.List;

/**
 * 患者健康指标纵向记录，按 patientId 归属。
 */
public interface HealthMetricRecordService {

    List<HealthMetricTypeVO> listTypes();

    HealthMetricTrendVO trend(Long patientId, String metricType, Integer range);

    HealthMetricRecordVO get(Long patientId, Long id);

    List<HealthMetricRecordVO> list(Long patientId, String metricType, Integer limit);

    HealthMetricRecordVO create(Long patientId, HealthMetricRecordDTO dto);

    HealthMetricRecordVO update(Long patientId, Long id, HealthMetricRecordDTO dto);

    void delete(Long patientId, Long id);
}
