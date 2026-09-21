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

class HealthMetricRecordRepositoryXmlTest {

    @Test
    void trendQueryIsPatientScopedOrderedByMeasuredAtAndExcludesDeleted() throws Exception {
        try (InputStream xml = getClass().getClassLoader()
                .getResourceAsStream("mapper/HealthMetricRecordRepository.xml")) {
            assertNotNull(xml);
            Document document = DocumentBuilderFactory.newInstance()
                    .newDocumentBuilder().parse(xml);
            document.getDocumentElement().normalize();

            Element trend = findById(document, "select", "selectTrend");
            String sql = trend.getTextContent();
            assertTrue(sql.contains("patient_id = #{patientId}"));
            assertFalse(sql.contains("user_id = #{userId}"));
            assertTrue(sql.contains("metric_type = #{metricType}"));
            assertTrue(sql.contains("is_deleted = 0"));
            assertTrue(sql.contains("measured_at"));
            assertTrue(sql.toLowerCase().contains("order by measured_at asc"));
            assertFalse(sql.toLowerCase().contains("order by created_at"));
        }
    }

    @Test
    void mutationsStayPatientScopedAndDeleteIsLogical() throws Exception {
        try (InputStream xml = getClass().getClassLoader()
                .getResourceAsStream("mapper/HealthMetricRecordRepository.xml")) {
            assertNotNull(xml);
            Document document = DocumentBuilderFactory.newInstance()
                    .newDocumentBuilder().parse(xml);
            String update = findById(document, "update", "updateByIdAndPatientId").getTextContent();
            String delete = findById(document, "update", "softDeleteByIdAndPatientId").getTextContent();
            assertTrue(update.contains("patient_id = #{patientId}"));
            assertTrue(update.contains("is_deleted = 0"));
            assertTrue(delete.contains("is_deleted = 1"));
            assertTrue(delete.contains("patient_id = #{patientId}"));
            assertFalse(update.contains("user_id = #{userId}"));
            assertFalse(delete.contains("user_id = #{userId}"));
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
