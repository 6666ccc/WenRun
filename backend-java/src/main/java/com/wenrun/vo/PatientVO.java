package com.wenrun.vo;

import lombok.Data;

import java.time.LocalDate;
import java.time.LocalDateTime;

/**
 * 患者视图对象
 */
@Data
public class PatientVO {

    private Long id;
    private String patientNo;
    private String name;
    private Integer gender;
    private LocalDate birthDate;
    private String idCard;
    private String phone;
    private Long userId;
    private String allergyHistory;
    private String address;
    private LocalDateTime createTime;
    private LocalDateTime updateTime;
}
