package com.wenrun.dto;

import jakarta.validation.constraints.NotNull;
import lombok.Data;

@Data
public class RegistrationRescheduleDTO {

    @NotNull
    private Long scheduleId;
}
