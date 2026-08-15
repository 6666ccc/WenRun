package com.wenrun.ai.dto;

import jakarta.validation.constraints.NotBlank;
import lombok.Data;

@Data
public class ChatRequestDTO {

    @NotBlank(message = "消息不能为空")
    private String message;

    /**
     * 会话唯一标识（必填）。
     * <p>前端每次新建对话时生成 UUID，同一对话窗口内所有请求共用。
     * AI 服务在 Qdrant 中以此字段作为过滤条件，确保记忆只检索当前会话的上下文，不会跨会话串数据。
     * </p>
     * <p>Python 侧收不到此字段时退化为无记忆模式，不报错。</p>
     */
    private String conversationId;

    /**
     * 是否启用记忆功能（可选）。
     * <p>敏感场景（如某些科室问诊）允许前端传 {@code false} 暂停记忆检索与存储。
     * 未传时默认启用记忆（AI 服务侧处理默认值）。</p>
     */
    private Boolean memoryEnabled;

    // ── 用户上下文（Java 从登录 Token 解析，供 AI 个性化，不传给 Python 作鉴权） ──
    private Long userId;
    private String username;
    private String realName;
    private String roleCode;
    private String portalType;

    // ── 医生端上下文 ──
    private Long staffId;

    // ── 患者端上下文 ──
    private Long patientId;
    private String patientNo;
    private String patientName;
    private Integer patientGender;
    private String patientBirthDate;
    private String patientAllergyHistory;
}
