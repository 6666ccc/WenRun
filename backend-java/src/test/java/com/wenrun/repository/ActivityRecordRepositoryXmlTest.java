package com.wenrun.repository;

import org.junit.jupiter.api.Test;
import org.w3c.dom.Document;
import org.w3c.dom.Element;
import org.w3c.dom.NodeList;

import javax.xml.parsers.DocumentBuilderFactory;
import java.io.InputStream;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

class ActivityRecordRepositoryXmlTest {

    @Test
    void exerciseQueriesStayPatientScopedAndDeleteIsLogical() throws Exception {
        Document document = load("mapper/PatientExerciseRecordRepository.xml");
        String recent = findById(document, "select", "selectRecent").getTextContent().toLowerCase();
        String since = findById(document, "select", "selectSince").getTextContent().toLowerCase();
        String update = findById(document, "update", "updateByIdAndPatientId").getTextContent();
        String delete = findById(document, "update", "softDeleteByIdAndPatientId").getTextContent();

        assertTrue(recent.contains("patient_id = #{patientid}"));
        assertTrue(recent.contains("is_deleted = 0"));
        assertTrue(recent.contains("order by started_at desc"));
        assertTrue(since.contains("started_at"));
        assertFalse(since.contains("order by created_at"));
        assertTrue(update.contains("patient_id = #{patientId}"));
        assertTrue(delete.contains("is_deleted = 1"));
        assertFalse(delete.contains("user_id = #{userId}"));
    }

    @Test
    void sleepQueriesUseWakeTimeAndStayPatientScoped() throws Exception {
        Document document = load("mapper/PatientSleepRecordRepository.xml");
        String since = findById(document, "select", "selectSince").getTextContent().toLowerCase();
        String recent = findById(document, "select", "selectRecent").getTextContent().toLowerCase();
        String delete = findById(document, "update", "softDeleteByIdAndPatientId").getTextContent();

        assertTrue(since.contains("wake_time"));
        assertTrue(since.contains("patient_id = #{patientid}"));
        assertTrue(since.contains("is_deleted = 0"));
        assertTrue(recent.contains("order by wake_time desc"));
        assertTrue(delete.contains("is_deleted = 1"));
        assertTrue(delete.contains("patient_id = #{patientId}"));
    }

    private static Document load(String path) throws Exception {
        try (InputStream xml = ActivityRecordRepositoryXmlTest.class.getClassLoader().getResourceAsStream(path)) {
            assertNotNull(xml);
            Document document = DocumentBuilderFactory.newInstance().newDocumentBuilder().parse(xml);
            document.getDocumentElement().normalize();
            return document;
        }
    }

    private static Element findById(Document document, String tag, String id) {
        NodeList nodes = document.getElementsByTagName(tag);
        for (int i = 0; i < nodes.getLength(); i++) {
            Element element = (Element) nodes.item(i);
            if (id.equals(element.getAttribute("id"))) {
                return element;
            }
        }
        throw new AssertionError("missing mapper id: " + id);
    }
}
