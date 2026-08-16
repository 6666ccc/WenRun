package com.wenrun.ai.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;

import java.time.Duration;

/**
 * AI 服务配置属性
 */
@Data
@ConfigurationProperties(prefix = "ai.service")
public class AiServiceProperties {

    /** FastAPI 根地址，如 http://127.0.0.1:8000 */
    private String baseUrl = "http://127.0.0.1:8000";

    /**
     * 服务间调用预共享密钥。
     * 对应配置项 {@code ai.service.api-key}，用于请求头 {@code X-Api-Key}。
     */
    private String apiKey = "";

    /** 聊天接口路径，对应 FastAPI POST /v1/chat */
    private String chatPath = "/v1/chat";

    /** 流式聊天路径，对应 FastAPI POST /v1/chat/stream */
    private String chatStreamPath = "/v1/chat/stream";

    /** 恢复 interrupt 的流式路径 */
    private String chatResumeStreamPath = "/v1/chat/resume/stream";

    /** Java 集成聊天路径，对应 FastAPI POST /java/chat（LangGraph 路由图） */
    private String javaChatPath = "/java/chat";

    /** 健康检查路径，对应 FastAPI GET /health */
    private String healthPath = "/health";

    /** 知识库文档入库路径，对应 FastAPI POST /v1/knowledge/ingest */
    private String knowledgeIngestPath = "/v1/knowledge/ingest";

    /** 知识库文档删除路径模板 */
    private String knowledgeDeletePath = "/v1/knowledge/{knowledgeBase}/{documentId}";

    /** 连接超时时间 */
    private Duration connectTimeout = Duration.ofSeconds(5);

    /** 同步聊天读取超时（流式接口按块读取，不受此限制） */
    private Duration readTimeout = Duration.ofSeconds(120);

    /** 流式聊天读取超时（单次 read 间隔） */
    private Duration streamReadTimeout = Duration.ofMinutes(10);
}
