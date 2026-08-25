package com.wenrun.dto;

import jakarta.validation.constraints.NotBlank;
import lombok.Data;
import lombok.ToString;

@Data
public class LoginDTO {
    @NotBlank(message = "用户名不能为空")
    private String username;
    @NotBlank(message = "密码不能为空")
    @ToString.Exclude
    private String password;
}
