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
    /** 绑定 sys_user（患者端登录） */
    private Long userId;
    private String allergyHistory;
    private String address;
    private LocalDateTime createTime;
    private LocalDateTime updateTime;
}
