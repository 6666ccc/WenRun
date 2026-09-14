package com.wenrun.ai.vo;

import com.fasterxml.jackson.annotation.JsonIgnore;
import com.wenrun.entity.ChatMessage;
import com.wenrun.entity.AiPatientMemory;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import lombok.Data;
import lombok.ToString;

import java.util.List;

@Data
public class aiRequest {

    @NotBlank(message = "消息不能为空")
    @Size(max = 2000, message = "消息长度不能超过 2000 个字符")
    @ToString.Exclude
    private String message;

    @Size(max = 64, message = "会话 ID 长度不能超过 64 个字符")
    private String conversationId;

    /** 由前端为同一轮对话生成的幂等键，不等同于 HTTP 链路追踪号。 */
    @Size(max = 64, message = "请求 ID 长度不能超过 64 个字符")
    private String clientRequestId;

    /**
     * 是否允许 Python AI 服务使用会话记忆；未传时由 Python 服务使用默认值。
     */
    private Boolean memoryEnabled;

    /**
     * 是否使用快速模式：跳过意图路由，由单个全能 Agent 直接作答。未传时按 false 处理。
     */
    private Boolean fastMode;

    /** 由 Java 鉴权上下文写入，不接受浏览器请求体覆盖。 */
    @JsonIgnore
    private Long userId;

    /** 由 Java 根据当前用户绑定的患者档案写入。 */
    @JsonIgnore
    private Long patientId;

    /** 捕获进入 Java 的追踪号，供异步 SSE 线程继续向 Python 透传。 */
    @JsonIgnore
    private String requestId;


    @JsonIgnore
    private String DelegatedToken;

    /** 仅在 Python checkpoint 丢失时使用的有限窗口，浏览器不能注入。 */
    @JsonIgnore
    private List<ChatMessage> recoveryMessages = List.of();

    /** Java 按 delegated patient 读取的 active 偏好；浏览器不能注入。 */
    @JsonIgnore
    private List<AiPatientMemory> longTermMemories = List.of();
}
