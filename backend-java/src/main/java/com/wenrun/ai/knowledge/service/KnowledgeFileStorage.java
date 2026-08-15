package com.wenrun.ai.knowledge.service;

import com.wenrun.ai.knowledge.config.KnowledgeStorageProperties;
import com.wenrun.ai.knowledge.model.KnowledgeBaseType;
import com.wenrun.common.exception.BusinessException;
import org.springframework.util.StringUtils;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

@Component
public class KnowledgeFileStorage {

    private static final Map<String, Set<String>> ALLOWED_MEDIA_TYPES = Map.of(
            "pdf", Set.of("application/pdf"),
            "docx", Set.of("application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
            "txt", Set.of("text/plain"),
            "md", Set.of("text/markdown", "text/plain")
    );

    private final Path root;
    private final long maxFileSize;

    public KnowledgeFileStorage(KnowledgeStorageProperties properties) {
        this.root = properties.getRoot().toAbsolutePath().normalize();
        this.maxFileSize = properties.getMaxFileSize().toBytes();
    }

    public StoredKnowledgeFile store(KnowledgeBaseType knowledgeBase, MultipartFile file) {
        String extension = validate(file);
        Path relativePath = Path.of(knowledgeBase.getPathValue(), UUID.randomUUID() + "." + extension);
        Path target = resolve(relativePath.toString());

        try {
            Files.createDirectories(target.getParent());
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            try (InputStream input = file.getInputStream(); OutputStream output = Files.newOutputStream(target)) {
                byte[] buffer = new byte[8192];
                long copied = 0;
                int read;
                while ((read = input.read(buffer)) != -1) {
                    copied += read;
                    if (copied > maxFileSize) {
                        throw new BusinessException("上传文件超过大小限制");
                    }
                    digest.update(buffer, 0, read);
                    output.write(buffer, 0, read);
                }
            }
            return new StoredKnowledgeFile(
                    target,
                    relativePath,
                    HexFormat.of().formatHex(digest.digest()),
                    extension);
        } catch (BusinessException ex) {
            deleteQuietly(target);
            throw ex;
        } catch (IOException | NoSuchAlgorithmException ex) {
            deleteQuietly(target);
            throw new BusinessException("知识库文件保存失败");
        }
    }

    public Path resolve(String relativePath) {
        Path resolved = root.resolve(relativePath).normalize();
        if (!resolved.startsWith(root)) {
            throw new BusinessException("非法的知识库文件路径");
        }
        return resolved;
    }

    public void delete(String relativePath) {
        try {
            Files.deleteIfExists(resolve(relativePath));
        } catch (IOException ex) {
            throw new BusinessException("知识库源文件删除失败");
        }
    }

    private String validate(MultipartFile file) {
        if (file == null || file.isEmpty()) {
            throw new BusinessException("上传文件不能为空");
        }
        if (file.getSize() > maxFileSize) {
            throw new BusinessException("上传文件超过大小限制");
        }

        String extension = StringUtils.getFilenameExtension(file.getOriginalFilename());
        if (!StringUtils.hasText(extension)) {
            throw new BusinessException("上传文件缺少扩展名");
        }
        extension = extension.toLowerCase(Locale.ROOT);
        Set<String> allowedTypes = ALLOWED_MEDIA_TYPES.get(extension);
        if (allowedTypes == null) {
            throw new BusinessException("仅支持 PDF、DOCX、TXT 和 Markdown 文件");
        }

        String contentType = file.getContentType();
        if (!StringUtils.hasText(contentType) || !allowedTypes.contains(contentType.toLowerCase(Locale.ROOT))) {
            throw new BusinessException("文件扩展名与 Content-Type 不匹配");
        }
        return extension;
    }

    private static void deleteQuietly(Path path) {
        try {
            Files.deleteIfExists(path);
        } catch (IOException ignored) {
            // Primary failure is more useful than cleanup failure here.
        }
    }

    public record StoredKnowledgeFile(
            Path absolutePath,
            Path relativePath,
            String sha256,
            String extension) {
    }
}
