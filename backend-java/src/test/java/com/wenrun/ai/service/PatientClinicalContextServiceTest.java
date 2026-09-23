package com.wenrun.ai.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.wenrun.ai.vo.PatientClinicalSource;
import com.wenrun.ai.vo.PatientDocumentCatalogItem;
import com.wenrun.common.exception.BusinessException;
import com.wenrun.entity.HealthMetricRecord;
import com.wenrun.entity.PatientHealthProfile;
import com.wenrun.repository.HealthMetricRecordRepository;
import com.wenrun.repository.PatientHealthProfileRepository;
import com.wenrun.repository.PatientMedicalDocumentRepository;
import com.wenrun.repository.PatientRepository;
import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.time.Clock;
import java.time.Instant;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

class PatientClinicalContextServiceTest {

    private final PatientRepository patientRepository = mock(PatientRepository.class);
    private final PatientHealthProfileRepository profileRepository = mock(PatientHealthProfileRepository.class);
    private final HealthMetricRecordRepository metricRepository = mock(HealthMetricRecordRepository.class);
    private final PatientMedicalDocumentRepository documentRepository = mock(PatientMedicalDocumentRepository.class);
    private final PatientClinicalContextService service = new PatientClinicalContextService(
            patientRepository,
            profileRepository,
            metricRepository,
            documentRepository,
            Clock.fixed(Instant.parse("2026-09-22T12:30:00Z"), PatientClinicalContextService.ZONE));

    @Test
    void usesEachMetricTimestampAndOmitsIdentity() throws Exception {
        PatientClinicalSource patient = new PatientClinicalSource();
        patient.setGender(1);
        patient.setBirthDate(LocalDate.of(1992, 3, 4));
        patient.setAllergyHistory("青霉素、13800138000");
        patient.setUpdateTime(LocalDateTime.of(2026, 9, 2, 9, 0));
        when(patientRepository.selectClinicalSource(11L)).thenReturn(patient);

        PatientHealthProfile profile = new PatientHealthProfile();
        profile.setHeightCm(new BigDecimal("170.0"));
        profile.setWaistCm(new BigDecimal("88.0"));
        profile.setSystolicMmhg(180);
        profile.setDiastolicMmhg(100);
        profile.setMeasuredAt(LocalDateTime.of(2019, 5, 5, 8, 0));
        profile.setPastHistory("见 https://bucket.cos.ap-shanghai.myqcloud.com/a.pdf?q-sign=abc 后手术");
        profile.setUpdateTime(LocalDateTime.of(2026, 9, 2, 9, 0));
        when(profileRepository.selectByPatientId(11L)).thenReturn(profile);
        when(metricRepository.selectRecent(11L, "BLOOD_PRESSURE", 30)).thenReturn(List.of(
                pressure("145", "92", LocalDateTime.of(2026, 9, 1, 8, 30)),
                pressure("140", "90", LocalDateTime.of(2026, 8, 1, 8, 30))));
        when(metricRepository.selectRecent(11L, "WEIGHT", 30)).thenReturn(List.of());
        when(metricRepository.selectRecent(11L, "WAIST", 30)).thenReturn(List.of());

        String json = new ObjectMapper().writeValueAsString(service.load(
                11L, "demographics,allergies,past_history,blood_pressure,anthropometrics"));

        assertTrue(json.contains("\"age\":34"));
        assertTrue(json.contains("\"recordedGender\":\"male\""));
        assertTrue(json.contains("145/92"));
        assertTrue(json.contains("2026-09-01T08:30:00+08:00"));
        assertTrue(json.contains("青霉素"));
        assertTrue(json.contains("后手术"));
        assertTrue(json.contains("timeBasis"));
        assertFalse(json.contains("1992-03-04"));
        assertFalse(json.contains("2019-05-05"));
        assertFalse(json.contains("13800138000"));
        assertFalse(json.contains("q-sign"));
        assertFalse(json.contains("https://"));
        assertFalse(json.contains("idCard"));
        assertFalse(json.contains("180/100"));
    }

    @Test
    void rejectsIdentityScopesBeforeReadingThePatient() {
        assertThrows(BusinessException.class, () -> service.load(11L, "id_card,phone,address"));
        assertThrows(BusinessException.class, () -> service.load(11L, ""));
        verifyNoInteractions(patientRepository, profileRepository, metricRepository, documentRepository);
    }

    @Test
    void documentCatalogListsTitlesWithoutFileLocations() throws Exception {
        when(patientRepository.selectClinicalSource(11L)).thenReturn(new PatientClinicalSource());
        PatientDocumentCatalogItem item = new PatientDocumentCatalogItem();
        item.setId(4L);
        item.setDocType("LAB_REPORT");
        item.setTitle("血常规");
        item.setOccurredAt(LocalDateTime.of(2026, 9, 20, 10, 0));
        when(documentRepository.selectCatalog(11L, 21)).thenReturn(List.of(item));

        String json = new ObjectMapper().writeValueAsString(service.load(11L, "document_catalog"));

        assertTrue(json.contains("血常规"));
        assertTrue(json.contains("LAB_REPORT"));
        assertTrue(json.contains("2026-09-20T10:00:00+08:00"));
        assertFalse(json.contains("files_json"));
        assertFalse(json.contains("http"));
        assertFalse(json.contains("url"));
    }

    @Test
    void clinicalQueriesDoNotSelectIdentityOrFileLocations() throws IOException {
        String patientXml = resource("/mapper/PatientRepository.xml");
        String clinicalQuery = extract(patientXml, "selectClinicalSource");
        assertFalse(clinicalQuery.contains("id_card"));
        assertFalse(clinicalQuery.contains("phone"));
        assertFalse(clinicalQuery.contains("address"));
        assertFalse(clinicalQuery.contains("patient_no"));
        assertTrue(clinicalQuery.contains("birth_date"));

        String documentXml = resource("/mapper/PatientMedicalDocumentRepository.xml");
        assertFalse(documentXml.contains("files_json"));
        assertFalse(documentXml.contains("url"));
        assertTrue(documentXml.contains("title"));
        assertTrue(documentXml.contains("occurred_at"));
    }

    private static HealthMetricRecord pressure(String systolic, String diastolic, LocalDateTime measuredAt) {
        HealthMetricRecord record = new HealthMetricRecord();
        record.setPrimaryValue(new BigDecimal(systolic));
        record.setSecondaryValue(new BigDecimal(diastolic));
        record.setMeasuredAt(measuredAt);
        record.setSourceType("MANUAL");
        return record;
    }

    private static String resource(String path) throws IOException {
        try (var input = PatientClinicalContextServiceTest.class.getResourceAsStream(path)) {
            if (input == null) {
                throw new IOException("missing " + path);
            }
            return new String(input.readAllBytes(), StandardCharsets.UTF_8);
        }
    }

    private static String extract(String xml, String id) {
        int start = xml.indexOf("id=\"" + id + "\"");
        int end = xml.indexOf("</select>", start);
        assertTrue(start >= 0 && end > start);
        return xml.substring(start, end);
    }
}
