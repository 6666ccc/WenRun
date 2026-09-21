package com.wenrun.service.impl;

import com.wenrun.common.constant.AccountType;
import com.wenrun.common.constant.BizStatus;
import com.wenrun.common.exception.BusinessException;
import com.wenrun.config.TokenSessionStore;
import com.wenrun.dto.LoginDTO;
import com.wenrun.dto.RegisterDTO;
import com.wenrun.dto.UpdateProfileDTO;
import com.wenrun.entity.Patient;
import com.wenrun.entity.Staff;
import com.wenrun.entity.SysRole;
import com.wenrun.entity.SysUser;
import com.wenrun.repository.PatientRepository;
import com.wenrun.repository.StaffRepository;
import com.wenrun.repository.SysUserRepository;
import com.wenrun.service.AuthService;
import com.wenrun.service.PatientAccessService;
import com.wenrun.service.PatientService;
import com.wenrun.service.support.LoginAssembler;
import com.wenrun.vo.AccessiblePatientVO;
import com.wenrun.vo.LoginVO;
import lombok.RequiredArgsConstructor;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import java.util.List;

@Service
@RequiredArgsConstructor
public class AuthServiceImpl implements AuthService {

    private final SysUserRepository sysUserMapper;
    private final StaffRepository staffMapper;
    private final PatientRepository patientMapper;
    private final PatientService patientService;
    private final PatientAccessService patientAccess;
    private final TokenSessionStore authTokenStore;
    private final PasswordEncoder passwordEncoder;

    @Override
    public LoginVO login(LoginDTO dto) {
        SysUser user = sysUserMapper.selectByUsername(dto.getUsername());
        if (user == null || user.getStatus() != BizStatus.ENABLED) {
            throw new BusinessException("用户名或密码错误");
        }
        if (!passwordEncoder.matches(dto.getPassword(), user.getPassword())) {
            throw new BusinessException("用户名或密码错误");
        }
        String token = authTokenStore.createToken(user.getId(), user.getAccountType());
        List<SysRole> roleList = sysUserMapper.selectRolesByUserId(user.getId());
        SysRole primaryRole = LoginAssembler.pickPrimaryRole(roleList);
        String portalType = LoginAssembler.resolvePortalType(user, primaryRole);

        LoginVO vo = new LoginVO();
        vo.setToken(token);
        vo.setUserId(user.getId());
        vo.setUsername(user.getUsername());
        vo.setRealName(user.getRealName());
        vo.setPortalType(portalType);
        vo.setUserType(portalType);
        vo.setRoles(roleList.stream().map(SysRole::getRoleCode).toList());
        if (primaryRole != null) {
            vo.setRoleCode(primaryRole.getRoleCode());
            vo.setRoleName(primaryRole.getRoleName());
        }
        fillBusinessIds(user, vo);
        return vo;
    }

    private void fillBusinessIds(SysUser user, LoginVO vo) {
        String accountType = user.getAccountType();
        if (!StringUtils.hasText(accountType)) {
            accountType = AccountType.INTERNAL;
        }
        if (AccountType.STAFF.equals(accountType)) {
            Staff staff = staffMapper.selectByUserId(user.getId());
            if (staff != null) {
                vo.setStaffId(staff.getId());
            }
            return;
        }
        if (AccountType.PATIENT.equals(accountType)) {
            List<AccessiblePatientVO> patients = patientAccess.listAccessible(user.getId());
            vo.setPatients(patients);
            Long defaultPatientId = patientAccess.defaultPatientId(user.getId());
            vo.setPatientId(defaultPatientId);
        }
    }

    @Override
    public void logout(String token) {
        if (StringUtils.hasText(token)) {
            authTokenStore.remove(token);
        }
    }

    @Override
    public Long resolveUserId(String token) {
        if (!StringUtils.hasText(token)) {
            throw new BusinessException("未登录");
        }
        Long userId = authTokenStore.getUserId(token);
        if (userId == null) {
            throw new BusinessException("Token 已过期或无效");
        }
        return userId;
    }

    @Override
    public void updateProfile(Long userId, UpdateProfileDTO dto) {
        SysUser user = sysUserMapper.selectById(userId);
        if (user == null) {
            throw new BusinessException("用户不存在");
        }

        // 更新 sys_user 基础信息
        boolean needUpdateUser = false;
        if (dto.getRealName() != null) {
            user.setRealName(dto.getRealName());
            needUpdateUser = true;
        }
        if (dto.getPhone() != null) {
            // 校验手机号唯一（排除自己）
            SysUser exist = sysUserMapper.selectByPhone(dto.getPhone());
            if (exist != null && !exist.getId().equals(userId)) {
                throw new BusinessException("手机号已被其他账号使用");
            }
            user.setPhone(dto.getPhone());
            needUpdateUser = true;
        }
        if (needUpdateUser) {
            sysUserMapper.updateById(user);
        }

        // 更新 patient 档案（仅患者端）
        if (AccountType.PATIENT.equals(user.getAccountType())) {
            Long patientId = patientAccess.defaultPatientId(userId);
            if (patientId == null) return;
            Patient patient = patientMapper.selectById(patientId);
            if (patient == null) return;

            boolean needUpdatePatient = false;
            if (dto.getRealName() != null) {
                patient.setName(dto.getRealName());
                needUpdatePatient = true;
            }
            if (dto.getPhone() != null) {
                patient.setPhone(dto.getPhone());
                needUpdatePatient = true;
            }
            if (dto.getGender() != null) {
                patient.setGender(dto.getGender());
                needUpdatePatient = true;
            }
            if (dto.getBirthDate() != null) {
                patient.setBirthDate(dto.getBirthDate());
                needUpdatePatient = true;
            }
            if (dto.getIdCard() != null) {
                patient.setIdCard(dto.getIdCard());
                needUpdatePatient = true;
            }
            if (dto.getAddress() != null) {
                patient.setAddress(dto.getAddress());
                needUpdatePatient = true;
            }
            if (dto.getAllergyHistory() != null) {
                patient.setAllergyHistory(dto.getAllergyHistory());
                needUpdatePatient = true;
            }
            if (needUpdatePatient) {
                patientMapper.updateById(patient);
            }
        }
    }

    @Override
    public LoginVO register(RegisterDTO dto) {
        // 1. 校验两次密码一致
        if (!dto.getPassword().equals(dto.getConfirmPassword())) {
            throw new BusinessException("两次输入的密码不一致");
        }

        // 2. 校验用户名唯一
        if (sysUserMapper.selectByUsername(dto.getUsername()) != null) {
            throw new BusinessException("用户名已被注册");
        }

        // 3. 校验手机号唯一
        if (sysUserMapper.selectByPhone(dto.getPhone()) != null) {
            throw new BusinessException("手机号已被注册");
        }

        // 4. 获取患者角色
        SysRole patientRole = sysUserMapper.selectRoleByCode("patient");
        if (patientRole == null) {
            throw new BusinessException("系统配置错误：患者角色不存在");
        }

        // 5. 创建系统用户（真实姓名注册时无需填写，由用户在个人中心补充）
        SysUser user = new SysUser();
        user.setUsername(dto.getUsername());
        user.setPassword(passwordEncoder.encode(dto.getPassword()));
        user.setPhone(dto.getPhone());
        user.setAccountType(AccountType.PATIENT);
        user.setStatus(BizStatus.ENABLED);
        sysUserMapper.insert(user);

        // 6. 分配患者角色
        sysUserMapper.insertUserRole(user.getId(), patientRole.getId());

        // 7. 自动创建患者档案（姓名暂用用户名占位，后续在个人中心完善）
        Patient patient = new Patient();
        patient.setName(dto.getUsername());
        patient.setPhone(dto.getPhone());
        patient.setGender(2); // 默认未知
        patient.setUserId(user.getId());
        patientService.create(patient);

        // 8. 生成 Token 并返回登录信息（注册即登录）
        String token = authTokenStore.createToken(user.getId(), user.getAccountType());
        List<SysRole> roleList = sysUserMapper.selectRolesByUserId(user.getId());
        SysRole primaryRole = LoginAssembler.pickPrimaryRole(roleList);
        String portalType = LoginAssembler.resolvePortalType(user, primaryRole);

        LoginVO vo = new LoginVO();
        vo.setToken(token);
        vo.setUserId(user.getId());
        vo.setUsername(user.getUsername());
        vo.setRealName(user.getRealName());
        vo.setPortalType(portalType);
        vo.setUserType(portalType);
        vo.setRoles(roleList.stream().map(SysRole::getRoleCode).toList());
        if (primaryRole != null) {
            vo.setRoleCode(primaryRole.getRoleCode());
            vo.setRoleName(primaryRole.getRoleName());
        }
        fillBusinessIds(user, vo);
        return vo;
    }
}
