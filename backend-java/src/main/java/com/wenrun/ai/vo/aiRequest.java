package com.wenrun.ai.vo;

import com.fasterxml.jackson.annotation.JsonIgnore;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import lombok.Data;
import lombok.ToString;

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
}
