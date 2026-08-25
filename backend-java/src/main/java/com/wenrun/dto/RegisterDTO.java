package com.wenrun.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import lombok.Data;
import lombok.ToString;

/**
 * 患者自助注册请求（真实姓名在注册后由用户在个人中心补充）
 */
@Data
public class RegisterDTO {

    @NotBlank(message = "用户名不能为空")
    private String username;

    @NotBlank(message = "密码不能为空")
    @Size(min = 6, message = "密码长度不能少于6位")
    @ToString.Exclude
    private String password;

    @NotBlank(message = "请确认密码")
    @ToString.Exclude
    private String confirmPassword;

    @NotBlank(message = "手机号不能为空")
    private String phone;
}
