package com.wenrun.ai.vo;

import lombok.Data;

import java.time.LocalDate;
import java.time.LocalDateTime;

/**
 * 临床上下文允许从 patient 表读出的列。不含姓名、证件、电话、地址和患者编号。
 */
@Data
public class PatientClinicalSource {

    private Integer gender;
    private LocalDate birthDate;
    private String allergyHistory;
    private LocalDateTime updateTime;
}
