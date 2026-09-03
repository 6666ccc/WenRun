package com.wenrun.ai.vo;

import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import lombok.Data;

/**
 * AI 代患者提交挂号的入参。
 * 故意不提供 patientId：患者维度只由委托令牌决定，Python 不能自选患者。
 */
@Data
public class AiRegistrationCreateRequest {

    @NotNull(message = "排班不能为空")
    private Long scheduleId;

    /** 幂等键，由 Python 用 会话 ID + 工具调用 ID 拼出，重放同一个键只会产生一张挂号单。 */
    @Size(max = 128, message = "幂等键长度不能超过 128 个字符")
    private String idempotencyKey;
}
