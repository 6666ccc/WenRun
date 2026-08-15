package com.wenrun.ai.knowledge.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;
import org.springframework.util.unit.DataSize;

import java.nio.file.Path;

@Data
@Component
@ConfigurationProperties(prefix = "ai.knowledge.storage")
public class KnowledgeStorageProperties {
    private Path root = Path.of("./data/knowledge");
    private DataSize maxFileSize = DataSize.ofMegabytes(20);
}
