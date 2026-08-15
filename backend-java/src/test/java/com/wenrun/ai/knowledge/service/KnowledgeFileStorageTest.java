package com.wenrun.ai.knowledge.service;

import com.wenrun.ai.knowledge.config.KnowledgeStorageProperties;
import com.wenrun.ai.knowledge.model.KnowledgeBaseType;
import com.wenrun.common.exception.BusinessException;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.util.unit.DataSize;

import java.nio.file.Files;
import java.nio.file.Path;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

class KnowledgeFileStorageTest {

    @TempDir
    Path tempRoot;

    private KnowledgeFileStorage storage;

    @BeforeEach
    void setUp() {
        KnowledgeStorageProperties properties = new KnowledgeStorageProperties();
        properties.setRoot(tempRoot);
        properties.setMaxFileSize(DataSize.ofBytes(16));
        storage = new KnowledgeFileStorage(properties);
    }

    @Test
    void storesFileBelowConfiguredRootAndComputesDigest() throws Exception {
        MockMultipartFile file = file("guide.txt", "text/plain", "hello");

        KnowledgeFileStorage.StoredKnowledgeFile stored = storage.store(
                KnowledgeBaseType.MEDICAL_GENERAL, file);

        assertTrue(stored.absolutePath().startsWith(tempRoot.toAbsolutePath()));
        assertEquals("medical-general", stored.relativePath().getName(0).toString());
        assertEquals("2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824",
                stored.sha256());
        assertEquals("hello", Files.readString(stored.absolutePath()));
    }

    @Test
    void neverUsesUntrustedOriginalNameAsStoragePath() {
        KnowledgeFileStorage.StoredKnowledgeFile stored = storage.store(
                KnowledgeBaseType.HOSPITAL_CUSTOM,
                file("../../outside.txt", "text/plain", "safe"));

        assertTrue(stored.absolutePath().startsWith(tempRoot.toAbsolutePath()));
        assertFalse(stored.absolutePath().toString().contains("outside.txt"));
    }

    @Test
    void rejectsEmptyUnsupportedMismatchedAndOversizedFiles() {
        assertThrows(BusinessException.class, () -> storage.store(
                KnowledgeBaseType.MEDICAL_GENERAL, file("empty.txt", "text/plain", "")));
        assertThrows(BusinessException.class, () -> storage.store(
                KnowledgeBaseType.MEDICAL_GENERAL, file("bad.exe", "application/octet-stream", "x")));
        assertThrows(BusinessException.class, () -> storage.store(
                KnowledgeBaseType.MEDICAL_GENERAL, file("bad.pdf", "text/plain", "x")));
        assertThrows(BusinessException.class, () -> storage.store(
                KnowledgeBaseType.MEDICAL_GENERAL,
                file("large.md", "text/markdown", "12345678901234567")));
    }

    @Test
    void resolvesAndDeletesOnlyManagedRelativePaths() throws Exception {
        KnowledgeFileStorage.StoredKnowledgeFile stored = storage.store(
                KnowledgeBaseType.MEDICAL_GENERAL, file("guide.md", "text/markdown", "content"));

        assertEquals(stored.absolutePath(), storage.resolve(stored.relativePath().toString()));
        storage.delete(stored.relativePath().toString());
        assertFalse(Files.exists(stored.absolutePath()));
        assertThrows(BusinessException.class, () -> storage.resolve("../outside.txt"));
    }

    private static MockMultipartFile file(String name, String contentType, String content) {
        return new MockMultipartFile("file", name, contentType, content.getBytes());
    }
}
