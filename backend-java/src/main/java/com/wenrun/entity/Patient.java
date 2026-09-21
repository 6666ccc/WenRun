package com.wenrun.entity;

import lombok.Data;

import java.time.LocalDate;
import java.time.LocalDateTime;

/**
 * 患者实体，对应表 patient
 */
@Data
public class Patient {

    private Long id;
    private String patientNo;
    private String name;
    /** 0女 1男 2未知 */
    private Integer gender;
    private LocalDate birthDate;
    private String idCard;
    private String phone;
    /** 主账号/创建账号，对应 sys_user.id；授权以 user_patient_relation 为准 */
    private Long userId;
    private String allergyHistory;
    private String address;
    private LocalDateTime createTime;
    private LocalDateTime updateTime;
}
