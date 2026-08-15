package com.wenrun.dto;

import lombok.Data;

import java.time.LocalDate;

/**
 * 个人资料更新请求
 */
@Data
public class UpdateProfileDTO {

    /** 真实姓名 */
    private String realName;

    /** 联系电话 */
    private String phone;

    /** 性别：0女 1男 2未知 */
    private Integer gender;

    /** 出生日期 */
    private LocalDate birthDate;

    /** 身份证号 */
    private String idCard;

    /** 住址 */
    private String address;

    /** 过敏史 */
    private String allergyHistory;
}
