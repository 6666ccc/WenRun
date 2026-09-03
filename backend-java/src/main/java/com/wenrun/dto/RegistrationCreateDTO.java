package com.wenrun.dto;

import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import lombok.Data;

@Data
public class RegistrationCreateDTO {
    @NotNull
    private Long patientId;
    @NotNull
    private Long scheduleId;
    /** 幂等键，重放同一个键只会产生一张挂号单。长度与 registration.idempotency_key 对齐。 */
    @Size(max = 128)
    private String idempotencyKey;
}
