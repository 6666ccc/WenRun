package com.wenrun.repository;

import org.junit.jupiter.api.Test;
import org.w3c.dom.Document;
import org.w3c.dom.Element;
import org.w3c.dom.NodeList;

import javax.xml.parsers.DocumentBuilderFactory;
import java.io.InputStream;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

class ChatMessageRepositoryXmlTest {

    @Test
    void conversationReadsAndDeletesAreAlwaysUserScoped() throws Exception {
        try (InputStream xml = getClass().getClassLoader()
                .getResourceAsStream("mapper/ChatMessageRepository.xml")) {
            assertNotNull(xml);
            Document document = DocumentBuilderFactory.newInstance()
                    .newDocumentBuilder().parse(xml);
            document.getDocumentElement().normalize();
            Set<String> scopedIds = Set.of(
                    "selectByConversationIdAndUserId",
                    "selectRecentByConversationIdAndUserId",
                    "selectPageByConversationIdAndUserId",
                    "selectByClientRequestId",
                    "deleteByConversationIdAndUserId",
                    "completeLatestConfirmation");
            for (String tag : Set.of("select", "delete", "update")) {
                NodeList nodes = document.getElementsByTagName(tag);
                for (int i = 0; i < nodes.getLength(); i++) {
                    Element element = (Element) nodes.item(i);
                    if (!scopedIds.contains(element.getAttribute("id"))) {
                        continue;
                    }
                    assertTrue(element.getTextContent().contains("user_id = #{userId}"),
                            element.getAttribute("id") + " 必须按 user_id 隔离");
                }
            }
        }
    }
}
