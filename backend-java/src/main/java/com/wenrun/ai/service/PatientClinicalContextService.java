package com.wenrun.ai.service;

import com.wenrun.ai.security.SensitiveText;
import com.wenrun.ai.vo.PatientClinicalContextVO;
import com.wenrun.ai.vo.PatientClinicalSource;
import com.wenrun.ai.vo.PatientDocumentCatalogItem;
import com.wenrun.common.ResultCode;
import com.wenrun.common.exception.BusinessException;
import com.wenrun.entity.HealthMetricRecord;
import com.wenrun.entity.PatientHealthProfile;
import com.wenrun.enums.HealthMetricType;
import com.wenrun.repository.HealthMetricRecordRepository;
import com.wenrun.repository.PatientHealthProfileRepository;
import com.wenrun.repository.PatientMedicalDocumentRepository;
import com.wenrun.repository.PatientRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.Clock;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.Period;
import java.time.ZoneId;
import java.time.ZonedDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

/**
 * 按白名单范围组装一次性临床摘录。指标时间来自 health_metric_record，
 * 不使用 patient_health_profile.measured_at，避免改一项体征让其他旧值看起来刚测过。
 */
@Service
public class PatientClinicalContextService {

    static final ZoneId ZONE = ZoneId.of("Asia/Shanghai");
    public static final Set<String> ALLOWED_SCOPES = Set.of(
            "demographics",
            "allergies",
            "past_history",
            "family_history",
            "personal_history",
            "anthropometrics",
            "blood_pressure",
            "blood_glucose",
            "heart_rate",
            "spo2",
            "temperature",
            "respiratory_rate",
            "document_catalog");

    private static final int METRIC_SAMPLE_LIMIT = 30;
    private static final int DOCUMENT_PAGE = 20;
    private static final DateTimeFormatter ISO_OFFSET = DateTimeFormatter.ISO_OFFSET_DATE_TIME;

    private final PatientRepository patientRepository;
    private final PatientHealthProfileRepository profileRepository;
    private final HealthMetricRecordRepository metricRepository;
    private final PatientMedicalDocumentRepository documentRepository;
    private final Clock clock;

    @Autowired
    public PatientClinicalContextService(
            PatientRepository patientRepository,
            PatientHealthProfileRepository profileRepository,
            HealthMetricRecordRepository metricRepository,
            PatientMedicalDocumentRepository documentRepository) {
        this(patientRepository, profileRepository, metricRepository, documentRepository, Clock.system(ZONE));
    }

    public PatientClinicalContextService(
            PatientRepository patientRepository,
            PatientHealthProfileRepository profileRepository,
            HealthMetricRecordRepository metricRepository,
            PatientMedicalDocumentRepository documentRepository,
            Clock clock) {
        this.patientRepository = patientRepository;
        this.profileRepository = profileRepository;
        this.metricRepository = metricRepository;
        this.documentRepository = documentRepository;
        this.clock = clock;
    }

    public PatientClinicalContextVO load(Long patientId, String scopes) {
        List<String> requested = parseScopes(scopes);
        PatientClinicalSource patient = patientRepository.selectClinicalSource(patientId);
        if (patient == null) {
            throw new BusinessException(ResultCode.NOT_FOUND, "没有找到患者档案");
        }
        PatientHealthProfile profile = needsProfile(requested)
                ? profileRepository.selectByPatientId(patientId) : null;

        PatientClinicalContextVO vo = new PatientClinicalContextVO();
        vo.setAsOf(ZonedDateTime.now(clock).format(ISO_OFFSET));
        Map<String, Object> facts = new LinkedHashMap<>();
        if (requested.contains("demographics")) {
            Map<String, Object> demographics = demographics(patient);
            if (!demographics.isEmpty()) {
                vo.setDemographics(demographics);
            }
        }
        if (requested.contains("allergies")) {
            put(facts, "allergies", allergies(patient));
        }
        if (requested.contains("past_history")) {
            put(facts, "pastHistory", history(profile == null ? null : profile.getPastHistory(), profile));
        }
        if (requested.contains("family_history")) {
            put(facts, "familyHistory", history(profile == null ? null : profile.getFamilyHistory(), profile));
        }
        if (requested.contains("personal_history")) {
            put(facts, "personalHistory", history(profile == null ? null : profile.getPersonalHistory(), profile));
        }
        if (requested.contains("anthropometrics")) {
            put(facts, "anthropometrics", anthropometrics(patientId, profile));
        }
        if (requested.contains("blood_pressure")) {
            put(facts, "latestBloodPressure", vital(patientId, HealthMetricType.BLOOD_PRESSURE, profile));
        }
        if (requested.contains("blood_glucose")) {
            put(facts, "latestBloodGlucose", vital(patientId, HealthMetricType.BLOOD_GLUCOSE, profile));
        }
        if (requested.contains("heart_rate")) {
            put(facts, "latestHeartRate", vital(patientId, HealthMetricType.HEART_RATE, profile));
        }
        if (requested.contains("spo2")) {
            put(facts, "latestSpo2", vital(patientId, HealthMetricType.SPO2, profile));
        }
        if (requested.contains("temperature")) {
            put(facts, "latestTemperature", vital(patientId, HealthMetricType.TEMPERATURE, profile));
        }
        if (requested.contains("respiratory_rate")) {
            put(facts, "latestRespiratoryRate", vital(patientId, HealthMetricType.RESPIRATORY_RATE, profile));
        }
        if (requested.contains("document_catalog")) {
            documents(patientId, facts);
        }
        if (!facts.isEmpty()) {
            vo.setRelevantClinicalFacts(facts);
        }
        return vo;
    }

    static List<String> parseScopes(String raw) {
        if (raw == null || raw.isBlank()) {
            throw new BusinessException("临床上下文范围不能为空");
        }
        LinkedHashSet<String> scopes = new LinkedHashSet<>();
        for (String part : raw.split(",")) {
            String scope = part.trim().toLowerCase(Locale.ROOT);
            if (scope.isEmpty()) {
                continue;
            }
            if (!ALLOWED_SCOPES.contains(scope)) {
                throw new BusinessException("不支持的临床上下文范围");
            }
            scopes.add(scope);
        }
        if (scopes.isEmpty()) {
            throw new BusinessException("临床上下文范围不能为空");
        }
        return List.copyOf(scopes);
    }

    private static boolean needsProfile(List<String> scopes) {
        for (String scope : scopes) {
            if (!"demographics".equals(scope) && !"allergies".equals(scope) && !"document_catalog".equals(scope)) {
                return true;
            }
        }
        return false;
    }

    private Map<String, Object> demographics(PatientClinicalSource patient) {
        Map<String, Object> demo = new LinkedHashMap<>();
        Integer age = age(patient.getBirthDate());
        if (age != null) {
            demo.put("age", age);
        }
        if (patient.getGender() != null) {
            demo.put("recordedGender", switch (patient.getGender()) {
                case 0 -> "female";
                case 1 -> "male";
                default -> "unknown";
            });
        }
        if (!demo.isEmpty()) {
            demo.put("source", "patient_record");
        }
        return demo;
    }

    private Integer age(LocalDate birthDate) {
        if (birthDate == null) {
            return null;
        }
        LocalDate today = LocalDate.now(clock);
        if (birthDate.isAfter(today)) {
            return null;
        }
        return Period.between(birthDate, today).getYears();
    }

    private Map<String, Object> allergies(PatientClinicalSource patient) {
        if (patient.getAllergyHistory() == null || patient.getAllergyHistory().isBlank()) {
            return null;
        }
        List<String> values = new ArrayList<>();
        for (String part : patient.getAllergyHistory().split("[、,，;；\\n|/]+")) {
            String cleaned = SensitiveText.cleanOrNull(part);
            if (cleaned != null && !values.contains(cleaned)) {
                values.add(cleaned);
            }
        }
        if (values.isEmpty()) {
            return null;
        }
        Map<String, Object> fact = new LinkedHashMap<>();
        fact.put("values", values);
        fact.put("source", "patient_record");
        stampRecordedAt(fact, patient.getUpdateTime(), "patient_record_updated_at");
        return fact;
    }

    private Map<String, Object> history(String text, PatientHealthProfile profile) {
        String cleaned = SensitiveText.cleanOrNull(text);
        if (cleaned == null) {
            return null;
        }
        Map<String, Object> fact = new LinkedHashMap<>();
        fact.put("text", cleaned);
        fact.put("source", "patient_health_profile");
        stampRecordedAt(fact, profile == null ? null : profile.getUpdateTime(), "profile_updated_at");
        return fact;
    }

    private Map<String, Object> anthropometrics(Long patientId, PatientHealthProfile profile) {
        List<HealthMetricRecord> weights = metricRepository.selectRecent(
                patientId, HealthMetricType.WEIGHT.getCode(), METRIC_SAMPLE_LIMIT);
        List<HealthMetricRecord> waists = metricRepository.selectRecent(
                patientId, HealthMetricType.WAIST.getCode(), METRIC_SAMPLE_LIMIT);
        Map<String, Object> body = new LinkedHashMap<>();
        BigDecimal height = profile == null ? null : profile.getHeightCm();
        BigDecimal weight = latestPrimary(weights);
        BigDecimal waist = latestPrimary(waists);
        if (height != null) {
            body.put("heightCm", untimedQuantity(decimal(height), "cm", "patient_health_profile"));
        }
        if (weight != null && weights != null && !weights.isEmpty()) {
            body.put("weightKg", fromRecords(HealthMetricType.WEIGHT, weights));
        } else if (profile != null && profile.getWeightKg() != null) {
            weight = profile.getWeightKg();
            body.put("weightKg", untimedQuantity(decimal(weight), "kg", "patient_health_profile"));
        }
        if (waist != null && waists != null && !waists.isEmpty()) {
            body.put("waistCm", fromRecords(HealthMetricType.WAIST, waists));
        } else if (profile != null && profile.getWaistCm() != null) {
            waist = profile.getWaistCm();
            body.put("waistCm", untimedQuantity(decimal(waist), "cm", "patient_health_profile"));
        }
        Map<String, Object> bmi = bmi(weight, height);
        if (bmi != null) {
            body.put("bmi", bmi);
        }
        Map<String, Object> whtr = whtr(waist, height);
        if (whtr != null) {
            body.put("whtr", whtr);
        }
        return body.isEmpty() ? null : body;
    }

    private Map<String, Object> vital(Long patientId, HealthMetricType type, PatientHealthProfile profile) {
        List<HealthMetricRecord> records = metricRepository.selectRecent(
                patientId, type.getCode(), METRIC_SAMPLE_LIMIT);
        if (records != null && !records.isEmpty()) {
            return fromRecords(type, records);
        }
        return profileFallback(type, profile);
    }

    private Map<String, Object> fromRecords(HealthMetricType type, List<HealthMetricRecord> records) {
        HealthMetricRecord latest = records.get(0);
        if (latest.getPrimaryValue() == null) {
            return null;
        }
        Map<String, Object> fact = new LinkedHashMap<>();
        if (type == HealthMetricType.BLOOD_PRESSURE) {
            fact.put("value", pressure(latest.getPrimaryValue(), latest.getSecondaryValue()));
            fact.put("unit", type.getUnit());
            HealthMetricRecord previous = records.size() > 1 ? records.get(1) : null;
            if (previous != null && previous.getPrimaryValue() != null) {
                Map<String, Integer> change = new LinkedHashMap<>();
                change.put("systolic", latest.getPrimaryValue().subtract(previous.getPrimaryValue()).intValue());
                if (latest.getSecondaryValue() != null && previous.getSecondaryValue() != null) {
                    change.put("diastolic", latest.getSecondaryValue().subtract(previous.getSecondaryValue()).intValue());
                }
                fact.put("changeFromPrevious", change);
            }
            fact.put("min", pressureExtreme(records, true));
            fact.put("max", pressureExtreme(records, false));
        } else {
            fact.put("value", decimal(latest.getPrimaryValue()));
            fact.put("unit", type.getUnit());
            if (records.size() > 1 && records.get(1).getPrimaryValue() != null) {
                fact.put("changeFromPrevious", decimal(
                        latest.getPrimaryValue().subtract(records.get(1).getPrimaryValue())));
            }
            BigDecimal min = null;
            BigDecimal max = null;
            for (HealthMetricRecord record : records) {
                BigDecimal value = record.getPrimaryValue();
                if (value == null) {
                    continue;
                }
                min = min == null || value.compareTo(min) < 0 ? value : min;
                max = max == null || value.compareTo(max) > 0 ? value : max;
            }
            if (min != null) {
                fact.put("min", decimal(min));
                fact.put("max", decimal(max));
            }
        }
        if (latest.getMeasureContext() != null && !latest.getMeasureContext().isBlank()) {
            fact.put("measureContext", latest.getMeasureContext());
        }
        String measuredAt = formatTime(latest.getMeasuredAt());
        if (measuredAt == null) {
            markUntimed(fact);
        } else {
            fact.put("measuredAt", measuredAt);
        }
        if (latest.getSourceType() != null && !latest.getSourceType().isBlank()) {
            fact.put("source", latest.getSourceType());
        }
        fact.put("sampleCount", records.size());
        return fact;
    }

    private Map<String, Object> profileFallback(HealthMetricType type, PatientHealthProfile profile) {
        if (profile == null) {
            return null;
        }
        Map<String, Object> fact = switch (type) {
            case BLOOD_PRESSURE -> profile.getSystolicMmhg() == null ? null : untimedQuantity(
                    pressure(BigDecimal.valueOf(profile.getSystolicMmhg()),
                            profile.getDiastolicMmhg() == null ? null : BigDecimal.valueOf(profile.getDiastolicMmhg())),
                    type.getUnit(), "patient_health_profile");
            case BLOOD_GLUCOSE -> profile.getGlucoseMmol() == null ? null : glucoseFallback(profile);
            case HEART_RATE -> profile.getHeartRateBpm() == null ? null : untimedQuantity(
                    String.valueOf(profile.getHeartRateBpm()), type.getUnit(), "patient_health_profile");
            case SPO2 -> profile.getSpo2Pct() == null ? null : untimedQuantity(
                    String.valueOf(profile.getSpo2Pct()), type.getUnit(), "patient_health_profile");
            case TEMPERATURE -> profile.getTemperatureC() == null ? null : untimedQuantity(
                    decimal(profile.getTemperatureC()), type.getUnit(), "patient_health_profile");
            case RESPIRATORY_RATE -> profile.getRespiratoryRateBpm() == null ? null : untimedQuantity(
                    String.valueOf(profile.getRespiratoryRateBpm()), type.getUnit(), "patient_health_profile");
            default -> null;
        };
        return fact;
    }

    private Map<String, Object> glucoseFallback(PatientHealthProfile profile) {
        Map<String, Object> fact = untimedQuantity(
                decimal(profile.getGlucoseMmol()), HealthMetricType.BLOOD_GLUCOSE.getUnit(), "patient_health_profile");
        if (profile.getGlucoseType() != null && !profile.getGlucoseType().isBlank()) {
            fact.put("measureContext", profile.getGlucoseType());
        }
        return fact;
    }

    private void documents(Long patientId, Map<String, Object> facts) {
        List<PatientDocumentCatalogItem> rows = documentRepository.selectCatalog(patientId, DOCUMENT_PAGE + 1);
        if (rows == null || rows.isEmpty()) {
            return;
        }
        boolean truncated = rows.size() > DOCUMENT_PAGE;
        List<Map<String, Object>> documents = new ArrayList<>();
        int limit = Math.min(rows.size(), DOCUMENT_PAGE);
        for (int index = 0; index < limit; index++) {
            PatientDocumentCatalogItem row = rows.get(index);
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("id", row.getId());
            item.put("docType", row.getDocType());
            String title = SensitiveText.cleanOrNull(row.getTitle());
            if (title != null) {
                item.put("title", title);
            }
            String occurredAt = formatTime(row.getOccurredAt());
            if (occurredAt != null) {
                item.put("occurredAt", occurredAt);
            }
            documents.add(item);
        }
        facts.put("documents", documents);
        if (truncated) {
            facts.put("documentListTruncated", true);
        }
    }

    private static Map<String, Object> untimedQuantity(String value, String unit, String source) {
        Map<String, Object> fact = new LinkedHashMap<>();
        fact.put("value", value);
        fact.put("unit", unit);
        fact.put("source", source);
        markUntimed(fact);
        return fact;
    }

    private static void markUntimed(Map<String, Object> fact) {
        fact.put("timeBasis", "unavailable");
        fact.put("note", "没有这项指标自己的测量时间，未使用档案的公共测量时间");
    }

    private static void stampRecordedAt(Map<String, Object> fact, LocalDateTime time, String basis) {
        String recordedAt = formatTime(time);
        if (recordedAt == null) {
            fact.put("timeBasis", "unavailable");
            return;
        }
        fact.put("recordedAt", recordedAt);
        fact.put("timeBasis", basis);
    }

    private static Map<String, Object> bmi(BigDecimal weightKg, BigDecimal heightCm) {
        if (weightKg == null || heightCm == null || heightCm.signum() <= 0) {
            return null;
        }
        BigDecimal meters = heightCm.divide(new BigDecimal("100"), 4, RoundingMode.HALF_UP);
        BigDecimal bmi = weightKg.divide(meters.multiply(meters), 1, RoundingMode.HALF_UP);
        Map<String, Object> fact = new LinkedHashMap<>();
        fact.put("value", bmi.toPlainString());
        fact.put("unit", "kg/m²");
        fact.put("source", "calculated");
        fact.put("basedOn", "latest_weight_and_profile_height");
        return fact;
    }

    private static Map<String, Object> whtr(BigDecimal waistCm, BigDecimal heightCm) {
        if (waistCm == null || heightCm == null || heightCm.signum() <= 0) {
            return null;
        }
        Map<String, Object> fact = new LinkedHashMap<>();
        fact.put("value", waistCm.divide(heightCm, 3, RoundingMode.HALF_UP).toPlainString());
        fact.put("unit", "ratio");
        fact.put("source", "calculated");
        fact.put("basedOn", "latest_waist_and_profile_height");
        return fact;
    }

    private static BigDecimal latestPrimary(List<HealthMetricRecord> records) {
        if (records == null || records.isEmpty() || records.get(0).getPrimaryValue() == null) {
            return null;
        }
        return records.get(0).getPrimaryValue();
    }

    private static Map<String, Integer> pressureExtreme(List<HealthMetricRecord> records, boolean minimum) {
        BigDecimal systolic = null;
        BigDecimal diastolic = null;
        for (HealthMetricRecord record : records) {
            if (record.getPrimaryValue() != null
                    && (systolic == null || (minimum
                    ? record.getPrimaryValue().compareTo(systolic) < 0
                    : record.getPrimaryValue().compareTo(systolic) > 0))) {
                systolic = record.getPrimaryValue();
            }
            if (record.getSecondaryValue() != null
                    && (diastolic == null || (minimum
                    ? record.getSecondaryValue().compareTo(diastolic) < 0
                    : record.getSecondaryValue().compareTo(diastolic) > 0))) {
                diastolic = record.getSecondaryValue();
            }
        }
        if (systolic == null && diastolic == null) {
            return null;
        }
        Map<String, Integer> extreme = new LinkedHashMap<>();
        if (systolic != null) {
            extreme.put("systolic", systolic.intValue());
        }
        if (diastolic != null) {
            extreme.put("diastolic", diastolic.intValue());
        }
        return extreme;
    }

    private static String pressure(BigDecimal systolic, BigDecimal diastolic) {
        if (diastolic == null) {
            return decimal(systolic);
        }
        return decimal(systolic) + "/" + decimal(diastolic);
    }

    private static String decimal(BigDecimal value) {
        return value.stripTrailingZeros().toPlainString();
    }

    private static String formatTime(LocalDateTime time) {
        if (time == null) {
            return null;
        }
        return time.atZone(ZONE).format(ISO_OFFSET);
    }

    private static void put(Map<String, Object> facts, String key, Map<String, Object> value) {
        if (value != null && !value.isEmpty()) {
            facts.put(key, value);
        }
    }
}
