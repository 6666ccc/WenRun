package com.wenrun.service.impl;

import com.wenrun.common.context.UserContext;
import com.wenrun.common.exception.BusinessException;
import com.wenrun.dto.HealthMetricRecordDTO;
import com.wenrun.entity.HealthMetricRecord;
import com.wenrun.entity.PatientHealthProfile;
import com.wenrun.enums.GlucoseMeasureContext;
import com.wenrun.enums.HealthMetricSourceType;
import com.wenrun.enums.HealthMetricType;
import com.wenrun.repository.HealthMetricRecordRepository;
import com.wenrun.repository.PatientHealthProfileRepository;
import com.wenrun.service.HealthMetricRecordService;
import com.wenrun.service.PatientAccessService;
import com.wenrun.util.HealthMetricBmi;
import com.wenrun.vo.HealthMetricPointVO;
import com.wenrun.vo.HealthMetricRecordVO;
import com.wenrun.vo.HealthMetricTrendVO;
import com.wenrun.vo.HealthMetricTypeVO;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.Arrays;
import java.util.List;
import java.util.Set;

/**
 * 健康指标纵向记录：按 patientId 归属，趋势按 measured_at 排序。
 */
@Service
@RequiredArgsConstructor
public class HealthMetricRecordServiceImpl implements HealthMetricRecordService {

    static final Set<Integer> TREND_RANGES = Set.of(7, 30, 90, 365);
    private static final int DEFAULT_RANGE = 30;
    private static final int DEFAULT_LIST_LIMIT = 50;
    private static final int MAX_LIST_LIMIT = 200;
    private static final int REMARK_MAX_LENGTH = 255;

    private final HealthMetricRecordRepository metricMapper;
    private final PatientHealthProfileRepository profileMapper;
    private final PatientAccessService patientAccess;

    @Override
    public List<HealthMetricTypeVO> listTypes() {
        return Arrays.stream(HealthMetricType.values())
                .map(this::toTypeVo)
                .toList();
    }

    @Override
    public HealthMetricTrendVO trend(Long patientId, String metricType, Integer range) {
        Long accessiblePatientId = patientAccess.requireAccessible(patientId).getId();
        HealthMetricType type = requireMetricType(metricType);
        int days = resolveRange(range);
        LocalDateTime fromTime = LocalDate.now().minusDays(days - 1L).atStartOfDay();

        HealthMetricTrendVO vo = new HealthMetricTrendVO();
        vo.setMetricType(type.getCode());
        vo.setMetricName(type.getDisplayName());
        vo.setUnit(type.getUnit());

        if (type == HealthMetricType.BMI) {
            fillBmiTrend(vo, accessiblePatientId, fromTime);
            return vo;
        }

        List<HealthMetricRecord> records = metricMapper.selectTrend(accessiblePatientId, type.getCode(), fromTime);
        vo.setRecords(records.stream().map(this::toPointVo).toList());
        if (!records.isEmpty()) {
            HealthMetricRecord latest = records.get(records.size() - 1);
            vo.setLatestValue(latest.getPrimaryValue());
            vo.setLatestSecondaryValue(latest.getSecondaryValue());
        }
        return vo;
    }

    @Override
    public HealthMetricRecordVO get(Long patientId, Long id) {
        return toRecordVo(requireOwned(patientId, id));
    }

    @Override
    public List<HealthMetricRecordVO> list(Long patientId, String metricType, Integer limit) {
        Long accessiblePatientId = patientAccess.requireAccessible(patientId).getId();
        String typeCode = null;
        if (StringUtils.hasText(metricType)) {
            HealthMetricType type = requireMetricType(metricType);
            if (!type.isPersisted()) {
                throw new BusinessException("BMI 由身高和体重动态计算，没有独立记录列表");
            }
            typeCode = type.getCode();
        }
        int size = resolveLimit(limit);
        return metricMapper.selectRecent(accessiblePatientId, typeCode, size).stream()
                .map(this::toRecordVo)
                .toList();
    }

    @Override
    @Transactional
    public HealthMetricRecordVO create(Long patientId, HealthMetricRecordDTO dto) {
        Long accessiblePatientId = patientAccess.requireAccessible(patientId).getId();
        HealthMetricRecord record = fromDto(dto);
        record.setPatientId(accessiblePatientId);
        record.setCreatedByUserId(UserContext.getUserId());
        metricMapper.insert(record);
        return toRecordVo(requireOwned(accessiblePatientId, record.getId()));
    }

    @Override
    @Transactional
    public HealthMetricRecordVO update(Long patientId, Long id, HealthMetricRecordDTO dto) {
        requireOwned(patientId, id);
        Long accessiblePatientId = patientAccess.requireAccessible(patientId).getId();
        HealthMetricRecord record = fromDto(dto);
        record.setId(id);
        record.setPatientId(accessiblePatientId);
        if (metricMapper.updateByIdAndPatientId(record) == 0) {
            throw new BusinessException("健康指标记录不存在");
        }
        return toRecordVo(requireOwned(accessiblePatientId, id));
    }

    @Override
    @Transactional
    public void delete(Long patientId, Long id) {
        requireOwned(patientId, id);
        if (metricMapper.softDeleteByIdAndPatientId(id, patientAccess.requireAccessible(patientId).getId()) == 0) {
            throw new BusinessException("健康指标记录不存在");
        }
    }

    private void fillBmiTrend(HealthMetricTrendVO vo, Long patientId, LocalDateTime fromTime) {
        BigDecimal heightCm = requireHeightCm(patientId);
        List<HealthMetricRecord> weights = metricMapper.selectTrend(
                patientId, HealthMetricType.WEIGHT.getCode(), fromTime);
        List<HealthMetricPointVO> points = weights.stream()
                .map(weight -> toBmiPoint(weight, heightCm))
                .filter(point -> point.getPrimaryValue() != null)
                .toList();
        vo.setRecords(points);
        if (!points.isEmpty()) {
            vo.setLatestValue(points.get(points.size() - 1).getPrimaryValue());
        }
    }

    private BigDecimal requireHeightCm(Long patientId) {
        PatientHealthProfile profile = profileMapper.selectByPatientId(patientId);
        if (profile == null || profile.getHeightCm() == null
                || profile.getHeightCm().compareTo(BigDecimal.ZERO) <= 0) {
            throw new BusinessException("请先完善患者档案中的身高后再查看 BMI 趋势");
        }
        return profile.getHeightCm();
    }

    private HealthMetricPointVO toBmiPoint(HealthMetricRecord weight, BigDecimal heightCm) {
        HealthMetricPointVO point = new HealthMetricPointVO();
        point.setPrimaryValue(HealthMetricBmi.calculate(weight.getPrimaryValue(), heightCm));
        point.setMeasuredAt(weight.getMeasuredAt());
        return point;
    }

    private HealthMetricRecord fromDto(HealthMetricRecordDTO dto) {
        HealthMetricRecordDTO source = dto == null ? new HealthMetricRecordDTO() : dto;
        HealthMetricType type = requirePersistedMetricType(source.getMetricType());
        HealthMetricSourceType sourceType = resolveSourceType(source.getSourceType());
        String measureContext = resolveMeasureContext(type, source.getMeasureContext());
        validateValues(type, source);

        HealthMetricRecord record = new HealthMetricRecord();
        record.setMetricType(type.getCode());
        record.setPrimaryValue(source.getPrimaryValue());
        record.setSecondaryValue(type == HealthMetricType.BLOOD_PRESSURE ? source.getSecondaryValue() : null);
        record.setMeasureContext(measureContext);
        record.setSourceType(sourceType.getCode());
        record.setMeasuredAt(source.getMeasuredAt());
        record.setRemark(blankToNull(source.getRemark()));
        return record;
    }

    private void validateValues(HealthMetricType type, HealthMetricRecordDTO dto) {
        if (dto.getPrimaryValue() == null) {
            throw new BusinessException("请填写指标值");
        }
        if (dto.getMeasuredAt() == null) {
            throw new BusinessException("请填写测量时间");
        }
        if (dto.getMeasuredAt().isAfter(LocalDateTime.now().plusMinutes(5))) {
            throw new BusinessException("测量时间不能晚于当前时间");
        }
        if (dto.getRemark() != null && dto.getRemark().length() > REMARK_MAX_LENGTH) {
            throw new BusinessException("备注不能超过 " + REMARK_MAX_LENGTH + " 字");
        }
        switch (type) {
            case WEIGHT -> requireRange(dto.getPrimaryValue(), "10", "300", "体重应在 10–300 kg");
            case WAIST -> requireRange(dto.getPrimaryValue(), "40", "200", "腰围应在 40–200 cm");
            case BLOOD_PRESSURE -> validateBloodPressure(dto);
            case BLOOD_GLUCOSE -> requireRange(dto.getPrimaryValue(), "1.0", "40.0", "血糖应在 1.0–40.0 mmol/L");
            case HEART_RATE -> requireRange(dto.getPrimaryValue(), "30", "220", "心率应在 30–220 次/分");
            case SPO2 -> requireRange(dto.getPrimaryValue(), "50", "100", "血氧应在 50–100 %");
            case TEMPERATURE -> requireRange(dto.getPrimaryValue(), "35.0", "42.0", "体温应在 35.0–42.0 ℃");
            case RESPIRATORY_RATE -> requireRange(dto.getPrimaryValue(), "8", "40", "呼吸频率应在 8–40 次/分");
            default -> throw new BusinessException("不支持写入该健康指标");
        }
    }

    private void validateBloodPressure(HealthMetricRecordDTO dto) {
        if (dto.getSecondaryValue() == null) {
            throw new BusinessException("血压请同时填写收缩压和舒张压");
        }
        requireRange(dto.getPrimaryValue(), "60", "250", "收缩压应在 60–250 mmHg");
        requireRange(dto.getSecondaryValue(), "40", "180", "舒张压应在 40–180 mmHg");
        if (dto.getPrimaryValue().compareTo(dto.getSecondaryValue()) <= 0) {
            throw new BusinessException("收缩压应高于舒张压");
        }
    }

    private void requireRange(BigDecimal value, String min, String max, String message) {
        if (value.compareTo(new BigDecimal(min)) < 0 || value.compareTo(new BigDecimal(max)) > 0) {
            throw new BusinessException(message);
        }
    }

    private HealthMetricType requireMetricType(String code) {
        return HealthMetricType.fromCode(code)
                .orElseThrow(() -> new BusinessException("不支持的健康指标类型"));
    }

    private HealthMetricType requirePersistedMetricType(String code) {
        HealthMetricType type = requireMetricType(code);
        if (!type.isPersisted()) {
            throw new BusinessException("BMI 由身高和体重动态计算，不能单独录入");
        }
        return type;
    }

    private HealthMetricSourceType resolveSourceType(String code) {
        if (!StringUtils.hasText(code)) {
            return HealthMetricSourceType.MANUAL;
        }
        return HealthMetricSourceType.fromCode(code)
                .orElseThrow(() -> new BusinessException("不支持的数据来源"));
    }

    private String resolveMeasureContext(HealthMetricType type, String code) {
        if (!StringUtils.hasText(code)) {
            return null;
        }
        if (type != HealthMetricType.BLOOD_GLUCOSE) {
            throw new BusinessException("测量场景仅用于血糖");
        }
        GlucoseMeasureContext context = GlucoseMeasureContext.fromCode(code)
                .orElseThrow(() -> new BusinessException("不支持的血糖测量场景"));
        return context.getCode();
    }

    private int resolveRange(Integer range) {
        int days = range == null ? DEFAULT_RANGE : range;
        if (!TREND_RANGES.contains(days)) {
            throw new BusinessException("时间范围仅支持 7 / 30 / 90 / 365 天");
        }
        return days;
    }

    private int resolveLimit(Integer limit) {
        int size = limit == null ? DEFAULT_LIST_LIMIT : limit;
        if (size < 1 || size > MAX_LIST_LIMIT) {
            throw new BusinessException("查询条数应在 1–" + MAX_LIST_LIMIT + " 之间");
        }
        return size;
    }

    private HealthMetricRecord requireOwned(Long patientId, Long id) {
        Long accessiblePatientId = patientAccess.requireAccessible(patientId).getId();
        if (id == null) {
            throw new BusinessException("健康指标记录不存在");
        }
        HealthMetricRecord record = metricMapper.selectByIdAndPatientId(id, accessiblePatientId);
        if (record == null) {
            throw new BusinessException("健康指标记录不存在");
        }
        return record;
    }

    private HealthMetricTypeVO toTypeVo(HealthMetricType type) {
        HealthMetricTypeVO vo = new HealthMetricTypeVO();
        vo.setMetricType(type.getCode());
        vo.setMetricName(type.getDisplayName());
        vo.setUnit(type.getUnit());
        vo.setDualLine(type.isDualLine());
        vo.setDerived(!type.isPersisted());
        return vo;
    }

    private HealthMetricPointVO toPointVo(HealthMetricRecord record) {
        HealthMetricPointVO point = new HealthMetricPointVO();
        point.setPrimaryValue(record.getPrimaryValue());
        point.setSecondaryValue(record.getSecondaryValue());
        point.setMeasureContext(record.getMeasureContext());
        point.setMeasuredAt(record.getMeasuredAt());
        return point;
    }

    private HealthMetricRecordVO toRecordVo(HealthMetricRecord record) {
        HealthMetricType type = requireMetricType(record.getMetricType());
        HealthMetricRecordVO vo = new HealthMetricRecordVO();
        vo.setId(record.getId());
        vo.setMetricType(type.getCode());
        vo.setMetricName(type.getDisplayName());
        vo.setUnit(type.getUnit());
        vo.setPrimaryValue(record.getPrimaryValue());
        vo.setSecondaryValue(record.getSecondaryValue());
        vo.setMeasureContext(record.getMeasureContext());
        vo.setSourceType(record.getSourceType());
        vo.setMeasuredAt(record.getMeasuredAt());
        vo.setRemark(record.getRemark());
        vo.setCreatedAt(record.getCreatedAt());
        vo.setUpdatedAt(record.getUpdatedAt());
        return vo;
    }

    private String blankToNull(String value) {
        return StringUtils.hasText(value) ? value.trim() : null;
    }
}
