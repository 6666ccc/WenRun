package com.wenrun.service.impl;

import com.wenrun.common.context.UserContext;
import com.wenrun.common.exception.BusinessException;
import com.wenrun.dto.HealthProfileDTO;
import com.wenrun.entity.HealthMetricRecord;
import com.wenrun.entity.PatientHealthProfile;
import com.wenrun.entity.PatientHealthSnapshot;
import com.wenrun.enums.GlucoseMeasureContext;
import com.wenrun.enums.HealthMetricSourceType;
import com.wenrun.enums.HealthMetricType;
import com.wenrun.repository.HealthMetricRecordRepository;
import com.wenrun.repository.PatientHealthProfileRepository;
import com.wenrun.repository.PatientHealthSnapshotRepository;
import com.wenrun.service.PatientAccessService;
import com.wenrun.service.PatientHealthProfileService;
import com.wenrun.vo.HealthProfileVO;
import com.wenrun.vo.HealthSnapshotVO;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.BeanUtils;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Objects;
import java.util.Set;

/**
 * 患者健康档案：当前值一对一，每次保存追加完整快照；
 * 有变化的体征同步写入 health_metric_record 供趋势图使用。
 */
@Service
@RequiredArgsConstructor
public class PatientHealthProfileServiceImpl implements PatientHealthProfileService {

    private static final Set<String> GLUCOSE_TYPES = Set.of("fasting", "random", "postprandial");
    private static final int HISTORY_MAX_LENGTH = 2000;

    private final PatientHealthProfileRepository profileMapper;
    private final PatientHealthSnapshotRepository snapshotMapper;
    private final HealthMetricRecordRepository metricMapper;
    private final PatientAccessService patientAccess;

    @Override
    public HealthProfileVO get(Long patientId) {
        patientAccess.assertAccess(patientId);
        PatientHealthProfile profile = profileMapper.selectByPatientId(patientId);
        return profile == null ? emptyVo(patientId) : toVo(profile);
    }

    @Override
    @Transactional
    public HealthProfileVO create(Long patientId, HealthProfileDTO dto) {
        patientAccess.assertAccess(patientId);
        if (profileMapper.selectByPatientId(patientId) != null) {
            throw new BusinessException("健康档案已存在，请使用更新");
        }
        PatientHealthProfile profile = fromDto(patientId, dto);
        profileMapper.insert(profile);
        insertSnapshot(profile);
        syncMetricRecords(patientId, null, profile);
        return toVo(requireCurrent(patientId));
    }

    @Override
    @Transactional
    public HealthProfileVO update(Long patientId, HealthProfileDTO dto) {
        patientAccess.assertAccess(patientId);
        PatientHealthProfile existing = profileMapper.selectByPatientId(patientId);
        if (existing == null) {
            throw new BusinessException("健康档案不存在，请先创建");
        }
        PatientHealthProfile profile = fromDto(patientId, dto);
        profile.setId(existing.getId());
        profileMapper.updateById(profile);
        insertSnapshot(profile);
        syncMetricRecords(patientId, existing, profile);
        return toVo(requireCurrent(patientId));
    }

    @Override
    @Transactional
    public void delete(Long patientId) {
        patientAccess.assertAccess(patientId);
        if (profileMapper.selectByPatientId(patientId) == null) {
            throw new BusinessException("健康档案不存在");
        }
        profileMapper.deleteByPatientId(patientId);
    }

    @Override
    public List<HealthSnapshotVO> listSnapshots(Long patientId) {
        patientAccess.assertAccess(patientId);
        return snapshotMapper.selectByPatientId(patientId).stream()
                .map(this::toSnapshotVo)
                .toList();
    }

    @Override
    @Transactional
    public void deleteSnapshot(Long patientId, Long snapshotId) {
        patientAccess.assertAccess(patientId);
        PatientHealthSnapshot snapshot = snapshotMapper.selectById(snapshotId);
        if (snapshot == null || !patientId.equals(snapshot.getPatientId())) {
            throw new BusinessException("快照不存在");
        }
        snapshotMapper.deleteById(snapshotId);
    }

    private PatientHealthProfile requireCurrent(Long patientId) {
        PatientHealthProfile profile = profileMapper.selectByPatientId(patientId);
        if (profile == null) {
            throw new BusinessException("健康档案不存在");
        }
        return profile;
    }

    private PatientHealthProfile fromDto(Long patientId, HealthProfileDTO dto) {
        HealthProfileDTO source = dto == null ? new HealthProfileDTO() : dto;
        normalize(source);
        validate(source);
        PatientHealthProfile profile = new PatientHealthProfile();
        BeanUtils.copyProperties(source, profile);
        profile.setPatientId(patientId);
        if (profile.getMeasuredAt() == null) {
            profile.setMeasuredAt(LocalDateTime.now());
        }
        return profile;
    }

    private void insertSnapshot(PatientHealthProfile profile) {
        PatientHealthSnapshot snapshot = new PatientHealthSnapshot();
        BeanUtils.copyProperties(profile, snapshot, "id", "createTime", "updateTime");
        snapshot.setId(null);
        snapshotMapper.insert(snapshot);
    }

    private void syncMetricRecords(Long patientId, PatientHealthProfile previous, PatientHealthProfile current) {
        if (patientId == null || current.getMeasuredAt() == null) {
            return;
        }
        boolean created = previous == null;
        if (current.getWeightKg() != null && (created || !sameDecimal(previous.getWeightKg(), current.getWeightKg()))) {
            insertMetric(patientId, HealthMetricType.WEIGHT.getCode(),
                    current.getWeightKg(), null, null, current.getMeasuredAt());
        }
        if (current.getWaistCm() != null && (created || !sameDecimal(previous.getWaistCm(), current.getWaistCm()))) {
            insertMetric(patientId, HealthMetricType.WAIST.getCode(),
                    current.getWaistCm(), null, null, current.getMeasuredAt());
        }
        if (current.getSystolicMmhg() != null && current.getDiastolicMmhg() != null
                && (created || !Objects.equals(previous.getSystolicMmhg(), current.getSystolicMmhg())
                || !Objects.equals(previous.getDiastolicMmhg(), current.getDiastolicMmhg()))) {
            insertMetric(patientId, HealthMetricType.BLOOD_PRESSURE.getCode(),
                    BigDecimal.valueOf(current.getSystolicMmhg()),
                    BigDecimal.valueOf(current.getDiastolicMmhg()),
                    null, current.getMeasuredAt());
        }
        if (current.getGlucoseMmol() != null
                && (created || !sameDecimal(previous.getGlucoseMmol(), current.getGlucoseMmol())
                || !Objects.equals(previous.getGlucoseType(), current.getGlucoseType()))) {
            insertMetric(patientId, HealthMetricType.BLOOD_GLUCOSE.getCode(),
                    current.getGlucoseMmol(), null, glucoseContext(current.getGlucoseType()), current.getMeasuredAt());
        }
        if (current.getHeartRateBpm() != null
                && (created || !Objects.equals(previous.getHeartRateBpm(), current.getHeartRateBpm()))) {
            insertMetric(patientId, HealthMetricType.HEART_RATE.getCode(),
                    BigDecimal.valueOf(current.getHeartRateBpm()), null, null, current.getMeasuredAt());
        }
        if (current.getSpo2Pct() != null
                && (created || !Objects.equals(previous.getSpo2Pct(), current.getSpo2Pct()))) {
            insertMetric(patientId, HealthMetricType.SPO2.getCode(),
                    BigDecimal.valueOf(current.getSpo2Pct()), null, null, current.getMeasuredAt());
        }
        if (current.getRespiratoryRateBpm() != null
                && (created || !Objects.equals(previous.getRespiratoryRateBpm(), current.getRespiratoryRateBpm()))) {
            insertMetric(patientId, HealthMetricType.RESPIRATORY_RATE.getCode(),
                    BigDecimal.valueOf(current.getRespiratoryRateBpm()), null, null, current.getMeasuredAt());
        }
        if (current.getTemperatureC() != null
                && (created || !sameDecimal(previous.getTemperatureC(), current.getTemperatureC()))) {
            insertMetric(patientId, HealthMetricType.TEMPERATURE.getCode(),
                    current.getTemperatureC(), null, null, current.getMeasuredAt());
        }
    }

    private void insertMetric(Long patientId, String metricType, BigDecimal primary, BigDecimal secondary,
                              String measureContext, LocalDateTime measuredAt) {
        HealthMetricRecord record = new HealthMetricRecord();
        record.setPatientId(patientId);
        record.setCreatedByUserId(UserContext.getUserId());
        record.setMetricType(metricType);
        record.setPrimaryValue(primary);
        record.setSecondaryValue(secondary);
        record.setMeasureContext(measureContext);
        record.setSourceType(HealthMetricSourceType.MANUAL.getCode());
        record.setMeasuredAt(measuredAt);
        metricMapper.insert(record);
    }

    private String glucoseContext(String glucoseType) {
        if (glucoseType == null) {
            return null;
        }
        return switch (glucoseType) {
            case "fasting" -> GlucoseMeasureContext.FASTING.getCode();
            case "random" -> GlucoseMeasureContext.RANDOM.getCode();
            case "postprandial" -> GlucoseMeasureContext.AFTER_MEAL_2H.getCode();
            default -> null;
        };
    }

    private boolean sameDecimal(BigDecimal left, BigDecimal right) {
        if (left == null && right == null) {
            return true;
        }
        if (left == null || right == null) {
            return false;
        }
        return left.compareTo(right) == 0;
    }

    private void normalize(HealthProfileDTO dto) {
        dto.setPastHistory(blankToNull(dto.getPastHistory()));
        dto.setFamilyHistory(blankToNull(dto.getFamilyHistory()));
        dto.setPersonalHistory(blankToNull(dto.getPersonalHistory()));
        dto.setGlucoseType(blankToNull(dto.getGlucoseType()));
        if (dto.getGlucoseType() != null) {
            dto.setGlucoseType(dto.getGlucoseType().trim().toLowerCase());
        }
    }

    private void validate(HealthProfileDTO dto) {
        if (!hasContent(dto)) {
            throw new BusinessException("请至少填写一项健康信息");
        }
        requireRange(dto.getHeightCm(), new BigDecimal("50.0"), new BigDecimal("250.0"), "身高应在 50–250 cm");
        requireRange(dto.getWeightKg(), new BigDecimal("10.0"), new BigDecimal("300.0"), "体重应在 10–300 kg");
        requireRange(dto.getWaistCm(), new BigDecimal("40.0"), new BigDecimal("200.0"), "腰围应在 40–200 cm");
        requireRange(dto.getSystolicMmhg(), 60, 250, "收缩压应在 60–250 mmHg");
        requireRange(dto.getDiastolicMmhg(), 40, 180, "舒张压应在 40–180 mmHg");
        if (dto.getSystolicMmhg() != null && dto.getDiastolicMmhg() != null
                && dto.getSystolicMmhg() <= dto.getDiastolicMmhg()) {
            throw new BusinessException("收缩压应高于舒张压");
        }
        requireRange(dto.getGlucoseMmol(), new BigDecimal("1.0"), new BigDecimal("40.0"), "血糖应在 1.0–40.0 mmol/L");
        if (dto.getGlucoseType() != null && !GLUCOSE_TYPES.contains(dto.getGlucoseType())) {
            throw new BusinessException("血糖类型仅支持 fasting / random / postprandial");
        }
        if (dto.getGlucoseType() != null && dto.getGlucoseMmol() == null) {
            throw new BusinessException("填写血糖类型时请同时填写血糖值");
        }
        requireRange(dto.getHeartRateBpm(), 30, 220, "心率应在 30–220 次/分");
        requireRange(dto.getSpo2Pct(), 50, 100, "血氧应在 50–100 %");
        requireRange(dto.getRespiratoryRateBpm(), 8, 40, "呼吸频率应在 8–40 次/分");
        requireRange(dto.getTemperatureC(), new BigDecimal("35.0"), new BigDecimal("42.0"), "体温应在 35.0–42.0 ℃");
        requireLength(dto.getPastHistory(), "既往史");
        requireLength(dto.getFamilyHistory(), "家族史");
        requireLength(dto.getPersonalHistory(), "个人史");
        if (dto.getMeasuredAt() != null && dto.getMeasuredAt().isAfter(LocalDateTime.now().plusMinutes(5))) {
            throw new BusinessException("测量时间不能晚于当前时间");
        }
    }

    private boolean hasContent(HealthProfileDTO dto) {
        return dto.getHeightCm() != null
                || dto.getWeightKg() != null
                || dto.getWaistCm() != null
                || dto.getSystolicMmhg() != null
                || dto.getDiastolicMmhg() != null
                || dto.getGlucoseMmol() != null
                || dto.getHeartRateBpm() != null
                || dto.getSpo2Pct() != null
                || dto.getRespiratoryRateBpm() != null
                || dto.getTemperatureC() != null
                || StringUtils.hasText(dto.getPastHistory())
                || StringUtils.hasText(dto.getFamilyHistory())
                || StringUtils.hasText(dto.getPersonalHistory());
    }

    private void requireRange(BigDecimal value, BigDecimal min, BigDecimal max, String message) {
        if (value != null && (value.compareTo(min) < 0 || value.compareTo(max) > 0)) {
            throw new BusinessException(message);
        }
    }

    private void requireRange(Integer value, int min, int max, String message) {
        if (value != null && (value < min || value > max)) {
            throw new BusinessException(message);
        }
    }

    private void requireLength(String value, String label) {
        if (value != null && value.length() > HISTORY_MAX_LENGTH) {
            throw new BusinessException(label + "不能超过 " + HISTORY_MAX_LENGTH + " 字");
        }
    }

    private String blankToNull(String value) {
        return StringUtils.hasText(value) ? value.trim() : null;
    }

    private HealthProfileVO emptyVo(Long patientId) {
        HealthProfileVO vo = new HealthProfileVO();
        vo.setPatientId(patientId);
        vo.setExists(false);
        return vo;
    }

    private HealthProfileVO toVo(PatientHealthProfile profile) {
        HealthProfileVO vo = new HealthProfileVO();
        BeanUtils.copyProperties(profile, vo);
        vo.setExists(true);
        return vo;
    }

    private HealthSnapshotVO toSnapshotVo(PatientHealthSnapshot snapshot) {
        HealthSnapshotVO vo = new HealthSnapshotVO();
        BeanUtils.copyProperties(snapshot, vo);
        return vo;
    }
}
