package com.wenrun.entity;

import lombok.Data;

import java.time.LocalDateTime;

@Data
public class DispenseRecord {
    private Long id;
    private Long prescriptionId;
    private Long pharmacistId;
    private LocalDateTime dispenseTime;
    private Integer status;
}
