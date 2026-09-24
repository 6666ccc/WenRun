package com.wenrun.service.impl;

import com.wenrun.common.context.UserContext;
import com.wenrun.common.exception.BusinessException;
import com.wenrun.dto.ExerciseRecordDTO;
import com.wenrun.dto.SleepRecordDTO;
import com.wenrun.entity.PatientExerciseRecord;
import com.wenrun.entity.PatientSleepRecord;
import com.wenrun.enums.ExerciseIntensity;
import com.wenrun.enums.ExerciseType;
import com.wenrun.enums.HealthMetricSourceType;
import com.wenrun.enums.SleepQuality;
import com.wenrun.repository.PatientExerciseRecordRepository;
import com.wenrun.repository.PatientSleepRecordRepository;
import com.wenrun.service.ActivityRecordService;
import com.wenrun.service.PatientAccessService;
import com.wenrun.vo.ActivityOptionVO;
import com.wenrun.vo.ActivityOptionsVO;
import com.wenrun.vo.ActivitySummaryVO;
import com.wenrun.vo.ExerciseRecordVO;
import com.wenrun.vo.SleepRecordVO;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.Duration;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.Arrays;
import java.util.List;
import java.util.Set;

/**
 * 患者运动与睡眠手动记录。统计按发生时间，睡眠时长由入睡与醒来时间计算。
 */
@Service
@RequiredArgsConstructor
public class ActivityRecordServiceImpl implements ActivityRecordService {

    static final Set<Integer> SUMMARY_RANGES = Set.of(7, 30);
    private static final int DEFAULT_RANGE = 7;
    private static final int DEFAULT_LIST_LIMIT = 20;
    private static final int MAX_LIST_LIMIT = 100;
    private static final int REMARK_MAX_LENGTH = 255;
    private static final int MIN_EXERCISE_MINUTES = 1;
    private static final int MAX_EXERCISE_MINUTES = 600;
    private static final int MIN_SLEEP_MINUTES = 10;
    private static final int MAX_SLEEP_MINUTES = 20 * 60;

    private final PatientExerciseRecordRepository exerciseMapper;
    private final PatientSleepRecordRepository sleepMapper;
    private final PatientAccessService patientAccess;

    @Override
    public ActivityOptionsVO options() {
        ActivityOptionsVO vo = new ActivityOptionsVO();
        vo.setExerciseTypes(Arrays.stream(ExerciseType.values())
                .map(type -> ActivityOptionVO.of(type.getCode(), type.getDisplayName()))
                .toList());
        vo.setIntensities(Arrays.stream(ExerciseIntensity.values())
                .map(type -> ActivityOptionVO.of(type.getCode(), type.getDisplayName()))
                .toList());
        vo.setSleepQualities(Arrays.stream(SleepQuality.values())
                .map(type -> ActivityOptionVO.of(String.valueOf(type.getScore()), type.getDisplayName()))
                .toList());
        return vo;
    }

    @Override
    public ActivitySummaryVO summary(Long patientId, Integer range) {
        Long accessiblePatientId = patientAccess.requireAccessible(patientId).getId();
        int days = resolveRange(range);
        LocalDateTime fromTime = LocalDate.now().minusDays(days - 1L).atStartOfDay();

        List<PatientExerciseRecord> exercises = exerciseMapper.selectSince(accessiblePatientId, fromTime);
        List<PatientSleepRecord> sleeps = sleepMapper.selectSince(accessiblePatientId, fromTime);

        ActivitySummaryVO vo = new ActivitySummaryVO();
        vo.setRangeDays(days);
        vo.setExerciseCount(exercises.size());
        vo.setExerciseMinutes(exercises.stream().mapToInt(PatientExerciseRecord::getDurationMin).sum());
        vo.setExerciseCalories(sumCalories(exercises));
        vo.setSleepCount(sleeps.size());
        vo.setSleepAvgMinutes(averageSleep(sleeps));
        vo.setLatestExercise(exerciseMapper.selectRecent(accessiblePatientId, 1).stream()
                .findFirst().map(this::toExerciseVo).orElse(null));
        vo.setLatestSleep(sleepMapper.selectRecent(accessiblePatientId, 1).stream()
                .findFirst().map(this::toSleepVo).orElse(null));
        return vo;
    }

    @Override
    public List<ExerciseRecordVO> listExercises(Long patientId, Integer limit) {
        Long accessiblePatientId = patientAccess.requireAccessible(patientId).getId();
        return exerciseMapper.selectRecent(accessiblePatientId, resolveLimit(limit)).stream()
                .map(this::toExerciseVo)
                .toList();
    }

    @Override
    public ExerciseRecordVO getExercise(Long patientId, Long id) {
        return toExerciseVo(requireExercise(patientId, id));
    }

    @Override
    @Transactional
    public ExerciseRecordVO createExercise(Long patientId, ExerciseRecordDTO dto) {
        Long accessiblePatientId = patientAccess.requireAccessible(patientId).getId();
        PatientExerciseRecord record = fromExerciseDto(dto);
        record.setPatientId(accessiblePatientId);
        record.setCreatedByUserId(UserContext.getUserId());
        exerciseMapper.insert(record);
        return toExerciseVo(requireExercise(accessiblePatientId, record.getId()));
    }

    @Override
    @Transactional
    public ExerciseRecordVO updateExercise(Long patientId, Long id, ExerciseRecordDTO dto) {
        requireExercise(patientId, id);
        Long accessiblePatientId = patientAccess.requireAccessible(patientId).getId();
        PatientExerciseRecord record = fromExerciseDto(dto);
        record.setId(id);
        record.setPatientId(accessiblePatientId);
        if (exerciseMapper.updateByIdAndPatientId(record) == 0) {
            throw new BusinessException("运动记录不存在");
        }
        return toExerciseVo(requireExercise(accessiblePatientId, id));
    }

    @Override
    @Transactional
    public void deleteExercise(Long patientId, Long id) {
        requireExercise(patientId, id);
        if (exerciseMapper.softDeleteByIdAndPatientId(id, patientAccess.requireAccessible(patientId).getId()) == 0) {
            throw new BusinessException("运动记录不存在");
        }
    }

    @Override
    public List<SleepRecordVO> listSleep(Long patientId, Integer limit) {
        Long accessiblePatientId = patientAccess.requireAccessible(patientId).getId();
        return sleepMapper.selectRecent(accessiblePatientId, resolveLimit(limit)).stream()
                .map(this::toSleepVo)
                .toList();
    }

    @Override
    public SleepRecordVO getSleep(Long patientId, Long id) {
        return toSleepVo(requireSleep(patientId, id));
    }

    @Override
    @Transactional
    public SleepRecordVO createSleep(Long patientId, SleepRecordDTO dto) {
        Long accessiblePatientId = patientAccess.requireAccessible(patientId).getId();
        PatientSleepRecord record = fromSleepDto(dto);
        record.setPatientId(accessiblePatientId);
        record.setCreatedByUserId(UserContext.getUserId());
        sleepMapper.insert(record);
        return toSleepVo(requireSleep(accessiblePatientId, record.getId()));
    }

    @Override
    @Transactional
    public SleepRecordVO updateSleep(Long patientId, Long id, SleepRecordDTO dto) {
        requireSleep(patientId, id);
        Long accessiblePatientId = patientAccess.requireAccessible(patientId).getId();
        PatientSleepRecord record = fromSleepDto(dto);
        record.setId(id);
        record.setPatientId(accessiblePatientId);
        if (sleepMapper.updateByIdAndPatientId(record) == 0) {
            throw new BusinessException("睡眠记录不存在");
        }
        return toSleepVo(requireSleep(accessiblePatientId, id));
    }

    @Override
    @Transactional
    public void deleteSleep(Long patientId, Long id) {
        requireSleep(patientId, id);
        if (sleepMapper.softDeleteByIdAndPatientId(id, patientAccess.requireAccessible(patientId).getId()) == 0) {
            throw new BusinessException("睡眠记录不存在");
        }
    }

    private PatientExerciseRecord fromExerciseDto(ExerciseRecordDTO dto) {
        ExerciseRecordDTO source = dto == null ? new ExerciseRecordDTO() : dto;
        ExerciseType type = ExerciseType.fromCode(source.getExerciseType())
                .orElseThrow(() -> new BusinessException("请选择运动类型"));
        if (source.getDurationMin() == null) {
            throw new BusinessException("请填写运动时长");
        }
        if (source.getDurationMin() < MIN_EXERCISE_MINUTES || source.getDurationMin() > MAX_EXERCISE_MINUTES) {
            throw new BusinessException("运动时长应在 1–600 分钟");
        }
        requireOccurredAt(source.getStartedAt(), "请填写运动开始时间", "运动开始时间不能晚于当前时间");
        requireRemark(source.getRemark());

        PatientExerciseRecord record = new PatientExerciseRecord();
        record.setExerciseType(type.getCode());
        record.setDurationMin(source.getDurationMin());
        record.setDistanceKm(normalizeDistance(source.getDistanceKm()));
        record.setCaloriesKcal(normalizeCalories(source.getCaloriesKcal()));
        record.setIntensity(normalizeIntensity(source.getIntensity()));
        record.setSourceType(resolveSourceType(source.getSourceType()).getCode());
        record.setStartedAt(source.getStartedAt());
        record.setRemark(blankToNull(source.getRemark()));
        return record;
    }

    private PatientSleepRecord fromSleepDto(SleepRecordDTO dto) {
        SleepRecordDTO source = dto == null ? new SleepRecordDTO() : dto;
        if (source.getBedtime() == null || source.getWakeTime() == null) {
            throw new BusinessException("请填写入睡时间和醒来时间");
        }
        if (!source.getWakeTime().isAfter(source.getBedtime())) {
            throw new BusinessException("醒来时间应晚于入睡时间");
        }
        requireOccurredAt(source.getBedtime(), "请填写入睡时间", "入睡时间不能晚于当前时间");
        if (source.getWakeTime().isAfter(LocalDateTime.now().plusMinutes(5))) {
            throw new BusinessException("醒来时间不能晚于当前时间");
        }
        long minutes = Duration.between(source.getBedtime(), source.getWakeTime()).toMinutes();
        if (minutes < MIN_SLEEP_MINUTES || minutes > MAX_SLEEP_MINUTES) {
            throw new BusinessException("睡眠时长应在 10 分钟到 20 小时之间");
        }
        SleepQuality quality = SleepQuality.fromScore(source.getQuality())
                .orElseThrow(() -> new BusinessException("请选择 1–5 的睡眠质量"));
        requireRemark(source.getRemark());

        PatientSleepRecord record = new PatientSleepRecord();
        record.setBedtime(source.getBedtime());
        record.setWakeTime(source.getWakeTime());
        record.setDurationMin((int) minutes);
        record.setQuality(quality.getScore());
        record.setSourceType(resolveSourceType(source.getSourceType()).getCode());
        record.setRemark(blankToNull(source.getRemark()));
        return record;
    }

    private BigDecimal normalizeDistance(BigDecimal distanceKm) {
        if (distanceKm == null) {
            return null;
        }
        if (distanceKm.compareTo(new BigDecimal("0.1")) < 0 || distanceKm.compareTo(new BigDecimal("300")) > 0) {
            throw new BusinessException("距离应在 0.1–300 公里");
        }
        return distanceKm.setScale(2, RoundingMode.HALF_UP);
    }

    private Integer normalizeCalories(Integer caloriesKcal) {
        if (caloriesKcal == null) {
            return null;
        }
        if (caloriesKcal < 1 || caloriesKcal > 8000) {
            throw new BusinessException("消耗热量应在 1–8000 千卡");
        }
        return caloriesKcal;
    }

    private String normalizeIntensity(String intensity) {
        if (!StringUtils.hasText(intensity)) {
            return null;
        }
        return ExerciseIntensity.fromCode(intensity)
                .orElseThrow(() -> new BusinessException("不支持的运动强度"))
                .getCode();
    }

    private void requireOccurredAt(LocalDateTime time, String missing, String future) {
        if (time == null) {
            throw new BusinessException(missing);
        }
        if (time.isAfter(LocalDateTime.now().plusMinutes(5))) {
            throw new BusinessException(future);
        }
    }

    private void requireRemark(String remark) {
        if (remark != null && remark.length() > REMARK_MAX_LENGTH) {
            throw new BusinessException("备注不能超过 " + REMARK_MAX_LENGTH + " 字");
        }
    }

    private HealthMetricSourceType resolveSourceType(String code) {
        if (!StringUtils.hasText(code)) {
            return HealthMetricSourceType.MANUAL;
        }
        return HealthMetricSourceType.fromCode(code)
                .orElseThrow(() -> new BusinessException("不支持的数据来源"));
    }

    private Integer sumCalories(List<PatientExerciseRecord> exercises) {
        List<Integer> values = exercises.stream()
                .map(PatientExerciseRecord::getCaloriesKcal)
                .filter(value -> value != null)
                .toList();
        if (values.isEmpty()) {
            return null;
        }
        return values.stream().mapToInt(Integer::intValue).sum();
    }

    private Integer averageSleep(List<PatientSleepRecord> sleeps) {
        if (sleeps.isEmpty()) {
            return null;
        }
        return (int) Math.round(sleeps.stream().mapToInt(PatientSleepRecord::getDurationMin).average().orElse(0));
    }

    private int resolveRange(Integer range) {
        if (range == null) {
            return DEFAULT_RANGE;
        }
        if (!SUMMARY_RANGES.contains(range)) {
            throw new BusinessException("汇总范围只支持近 7 天或近 30 天");
        }
        return range;
    }

    private int resolveLimit(Integer limit) {
        if (limit == null) {
            return DEFAULT_LIST_LIMIT;
        }
        if (limit < 1 || limit > MAX_LIST_LIMIT) {
            throw new BusinessException("列表条数应在 1–" + MAX_LIST_LIMIT);
        }
        return limit;
    }

    private PatientExerciseRecord requireExercise(Long patientId, Long id) {
        Long accessiblePatientId = patientAccess.requireAccessible(patientId).getId();
        PatientExerciseRecord record = exerciseMapper.selectByIdAndPatientId(id, accessiblePatientId);
        if (record == null) {
            throw new BusinessException("运动记录不存在");
        }
        return record;
    }

    private PatientSleepRecord requireSleep(Long patientId, Long id) {
        Long accessiblePatientId = patientAccess.requireAccessible(patientId).getId();
        PatientSleepRecord record = sleepMapper.selectByIdAndPatientId(id, accessiblePatientId);
        if (record == null) {
            throw new BusinessException("睡眠记录不存在");
        }
        return record;
    }

    private ExerciseRecordVO toExerciseVo(PatientExerciseRecord record) {
        ExerciseType type = ExerciseType.fromCode(record.getExerciseType()).orElse(null);
        ExerciseIntensity intensity = ExerciseIntensity.fromCode(record.getIntensity()).orElse(null);
        ExerciseRecordVO vo = new ExerciseRecordVO();
        vo.setId(record.getId());
        vo.setExerciseType(record.getExerciseType());
        vo.setExerciseName(type == null ? record.getExerciseType() : type.getDisplayName());
        vo.setDurationMin(record.getDurationMin());
        vo.setDistanceKm(record.getDistanceKm());
        vo.setCaloriesKcal(record.getCaloriesKcal());
        vo.setIntensity(record.getIntensity());
        vo.setIntensityName(intensity == null ? null : intensity.getDisplayName());
        vo.setSourceType(record.getSourceType());
        vo.setStartedAt(record.getStartedAt());
        vo.setRemark(record.getRemark());
        vo.setCreatedAt(record.getCreatedAt());
        vo.setUpdatedAt(record.getUpdatedAt());
        return vo;
    }

    private SleepRecordVO toSleepVo(PatientSleepRecord record) {
        SleepQuality quality = SleepQuality.fromScore(record.getQuality()).orElse(null);
        SleepRecordVO vo = new SleepRecordVO();
        vo.setId(record.getId());
        vo.setBedtime(record.getBedtime());
        vo.setWakeTime(record.getWakeTime());
        vo.setDurationMin(record.getDurationMin());
        vo.setQuality(record.getQuality());
        vo.setQualityName(quality == null ? null : quality.getDisplayName());
        vo.setSourceType(record.getSourceType());
        vo.setRemark(record.getRemark());
        vo.setCreatedAt(record.getCreatedAt());
        vo.setUpdatedAt(record.getUpdatedAt());
        return vo;
    }

    private String blankToNull(String value) {
        if (!StringUtils.hasText(value)) {
            return null;
        }
        return value.trim();
    }
}
