-- WenRun 种子数据（可重复执行）
-- 管理员: liuchang / liu123456789 / 17539861379
-- 密码为 BCrypt（与 Spring BCryptPasswordEncoder 兼容）
-- 中文使用 UNHEX，避免 Windows 客户端编码丢失

USE wenrun;

SET NAMES utf8mb4;

-- 基础角色（注册患者、登录门户解析依赖）
INSERT INTO sys_role (role_code, role_name, default_portal)
VALUES
  ('admin', CONVERT(UNHEX('E7AEA1E79086E59198') USING utf8mb4), 'admin'),
  ('doctor', CONVERT(UNHEX('E58CBBE7949F') USING utf8mb4), 'doctor'),
  ('patient', CONVERT(UNHEX('E682A3E88085') USING utf8mb4), 'patient')
ON DUPLICATE KEY UPDATE
  role_name = VALUES(role_name),
  default_portal = VALUES(default_portal);

-- 管理员账户
INSERT INTO sys_user (
  username, password, real_name, phone, phone_verified, account_type, status
) VALUES (
  'liuchang',
  '$2b$10$S4y2pi5jMKm.yjfWEVaNbO4PBIvkssjlfnyycjqi/6M6O3.Y9dPm2',
  CONVERT(UNHEX('E58898E79585') USING utf8mb4),
  '17539861379',
  1,
  'internal',
  1
)
ON DUPLICATE KEY UPDATE
  password = VALUES(password),
  real_name = VALUES(real_name),
  phone = VALUES(phone),
  phone_verified = VALUES(phone_verified),
  account_type = VALUES(account_type),
  status = VALUES(status);

-- 绑定管理员角色
INSERT IGNORE INTO sys_user_role (user_id, role_id)
SELECT u.id, r.id
FROM sys_user u
JOIN sys_role r ON r.role_code = 'admin'
WHERE u.username = 'liuchang';
