package com.wenrun.dto;

import jakarta.validation.constraints.NotNull;
import lombok.Data;

@Data
public class ExamRequestCreateDTO {
    @NotNull
    private Long visitId;
    @NotNull
    private Long itemId;
}
