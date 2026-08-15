package com.wenrun.ai.knowledge.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

import java.time.Duration;

@Data
@Component
@ConfigurationProperties(prefix = "ai.knowledge.tasks")
public class KnowledgeTaskProperties {
    private int corePoolSize = 2;
    private int maxPoolSize = 4;
    private int queueCapacity = 100;
    private Duration staleAfter = Duration.ofMinutes(30);
}
