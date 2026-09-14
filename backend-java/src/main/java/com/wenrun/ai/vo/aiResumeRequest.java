package com.wenrun.ai.vo;

import com.fasterxml.jackson.annotation.JsonIgnore;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;
import lombok.Data;

/** 患者在确认卡片上作出选择后，恢复被挂起的那一轮对话。 */
@Data
public class aiResumeRequest {

    @NotBlank(message = "会话 ID 不能为空")
    @Size(max = 64, message = "会话 ID 长度不能超过 64 个字符")
    private String conversationId;

    @NotBlank(message = "确认结果不能为空")
    @Pattern(regexp = "approve|reject", message = "确认结果只能是 approve 或 reject")
    private String decision;

    /** 前端从 confirm 事件原样带回，用于在多个挂起 interrupt 中精确续跑。 */
    @Size(max = 128, message = "中断 ID 长度不能超过 128 个字符")
    private String interruptId;

    /** 恢复也是独立的一轮，需要自己的幂等键，不能复用被挂起那一轮的。 */
    @Size(max = 64, message = "请求 ID 长度不能超过 64 个字符")
    private String clientRequestId;

    /** 由 Java 鉴权上下文写入，不接受浏览器请求体覆盖。 */
    @JsonIgnore
    private Long userId;

    @JsonIgnore
    private Long patientId;

    @JsonIgnore
    private String requestId;

    @JsonIgnore
    private String DelegatedToken;
}
