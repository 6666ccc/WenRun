package com.wenrun.repository;

import org.junit.jupiter.api.Test;
import org.w3c.dom.Document;

import javax.xml.parsers.DocumentBuilderFactory;
import java.io.InputStream;

import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

class ScheduleRepositoryXmlTest {

    @Test
    void mapperDeclaresSelectVOByIdUsedByGetDetail() throws Exception {
        try (InputStream xml = getClass().getClassLoader()
                .getResourceAsStream("mapper/ScheduleRepository.xml")) {
            assertNotNull(xml);
            Document document = DocumentBuilderFactory.newInstance().newDocumentBuilder().parse(xml);
            document.getDocumentElement().normalize();
            var nodes = document.getElementsByTagName("select");
            boolean found = false;
            for (int i = 0; i < nodes.getLength(); i++) {
                if ("selectVOById".equals(nodes.item(i).getAttributes().getNamedItem("id").getNodeValue())) {
                    found = true;
                    break;
                }
            }
            assertTrue(found, "ScheduleRepository.xml 缺少 selectVOById，按 id 查排班会 BindingException");
        }
    }
}
