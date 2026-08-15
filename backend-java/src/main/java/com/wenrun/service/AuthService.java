package com.wenrun.service;

import com.wenrun.dto.LoginDTO;
import com.wenrun.dto.RegisterDTO;
import com.wenrun.dto.UpdateProfileDTO;
import com.wenrun.vo.LoginVO;

public interface AuthService {

    LoginVO login(LoginDTO dto);

    void logout(String token);

    LoginVO register(RegisterDTO dto);

    /** 更新个人资料 */
    void updateProfile(Long userId, UpdateProfileDTO dto);

    /** 根据 Token 解析用户 ID */
    Long resolveUserId(String token);
}
