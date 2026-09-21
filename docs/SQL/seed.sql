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

-- ---------------------------------------------------------------------------
-- 挂号兼容基础数据：门诊科室 + 专家
-- 中文一律 UNHEX，避免 Windows 客户端编码丢失
-- ---------------------------------------------------------------------------
INSERT INTO dept (dept_code, dept_name, parent_id, status) VALUES
  ('DEPT_IM',   CONVERT(UNHEX('E58685E7A791') USING utf8mb4),     NULL, 1),
  ('DEPT_GS',   CONVERT(UNHEX('E5A496E7A791') USING utf8mb4),     NULL, 1),
  ('DEPT_PED',  CONVERT(UNHEX('E584BFE7A791') USING utf8mb4),     NULL, 1),
  ('DEPT_OB',   CONVERT(UNHEX('E5A687E4BAA7E7A791') USING utf8mb4), NULL, 1),
  ('DEPT_ORT',  CONVERT(UNHEX('E9AAA8E7A791') USING utf8mb4),     NULL, 1),
  ('DEPT_DERM', CONVERT(UNHEX('E79AAEE882A4E7A791') USING utf8mb4), NULL, 1),
  ('DEPT_OPH',  CONVERT(UNHEX('E79CBCE7A791') USING utf8mb4),     NULL, 1),
  ('DEPT_ENT',  CONVERT(UNHEX('E880B3E9BCBBE59689E7A791') USING utf8mb4), NULL, 1)
ON DUPLICATE KEY UPDATE
  dept_name = VALUES(dept_name),
  status = VALUES(status);

INSERT INTO staff (staff_no, name, dept_id, title, user_id, status)
SELECT v.staff_no, v.name, d.id, v.title, NULL, 1
FROM (
  SELECT 'D001' staff_no, CONVERT(UNHEX('E5BCA0E4BC9F') USING utf8mb4) name, 'DEPT_IM' dept_code, CONVERT(UNHEX('E4B8BBE4BBBBE58CBBE5B888') USING utf8mb4) title UNION ALL
  SELECT 'D002', CONVERT(UNHEX('E69D8EE5A89C') USING utf8mb4), 'DEPT_IM', CONVERT(UNHEX('E4B8BBE6B2BBE58CBBE5B888') USING utf8mb4) UNION ALL
  SELECT 'D003', CONVERT(UNHEX('E78E8BE5BCBA') USING utf8mb4), 'DEPT_GS', CONVERT(UNHEX('E4B8BBE4BBBBE58CBBE5B888') USING utf8mb4) UNION ALL
  SELECT 'D004', CONVERT(UNHEX('E8B5B5E6958F') USING utf8mb4), 'DEPT_PED', CONVERT(UNHEX('E4B8BBE6B2BBE58CBBE5B888') USING utf8mb4) UNION ALL
  SELECT 'D005', CONVERT(UNHEX('E99988E99D99') USING utf8mb4), 'DEPT_OB', CONVERT(UNHEX('E589AFE4B8BBE4BBBBE58CBBE5B888') USING utf8mb4) UNION ALL
  SELECT 'D006', CONVERT(UNHEX('E58898E6B48B') USING utf8mb4), 'DEPT_ORT', CONVERT(UNHEX('E4B8BBE6B2BBE58CBBE5B888') USING utf8mb4) UNION ALL
  SELECT 'D007', CONVERT(UNHEX('E591A8E88AB3') USING utf8mb4), 'DEPT_DERM', CONVERT(UNHEX('E4B8BBE6B2BBE58CBBE5B888') USING utf8mb4) UNION ALL
  SELECT 'D008', CONVERT(UNHEX('E590B4E7A38A') USING utf8mb4), 'DEPT_OPH', CONVERT(UNHEX('E4B8BBE6B2BBE58CBBE5B888') USING utf8mb4) UNION ALL
  SELECT 'D009', CONVERT(UNHEX('E98391E587AF') USING utf8mb4), 'DEPT_ENT', CONVERT(UNHEX('E4B8BBE6B2BBE58CBBE5B888') USING utf8mb4)
) v
JOIN dept d ON d.dept_code = v.dept_code
ON DUPLICATE KEY UPDATE
  name = VALUES(name),
  dept_id = VALUES(dept_id),
  title = VALUES(title),
  status = VALUES(status);

-- ---------------------------------------------------------------------------
-- 号源：固定从 2026-09-19 排到 2026-10-19（含），不要用 CURDATE()
-- 8 个门诊科室每位专家每天上午/下午 20 号；张伟另加晚上 10 号
-- ---------------------------------------------------------------------------
INSERT INTO schedule (dept_id, staff_id, work_date, time_period, total_count, remaining_count, register_fee)
SELECT st.dept_id, st.id, days.work_date, periods.p, 20, 20,
  CASE HEX(st.title)
    WHEN 'E4B8BBE4BBBBE58CBBE5B888' THEN 50.00
    WHEN 'E589AFE4B8BBE4BBBBE58CBBE5B888' THEN 35.00
    WHEN 'E4B8BBE6B2BBE58CBBE5B888' THEN 25.00
    ELSE 15.00
  END
FROM staff st
JOIN dept d ON d.id = st.dept_id
JOIN (
  WITH RECURSIVE days AS (
    SELECT DATE('2026-09-19') AS work_date
    UNION ALL
    SELECT DATE_ADD(work_date, INTERVAL 1 DAY) FROM days WHERE work_date < DATE('2026-10-19')
  )
  SELECT work_date FROM days
) days
JOIN (
  SELECT CONVERT(UNHEX('E4B88AE58D88') USING utf8mb4) COLLATE utf8mb4_unicode_ci AS p
  UNION ALL
  SELECT CONVERT(UNHEX('E4B88BE58D88') USING utf8mb4) COLLATE utf8mb4_unicode_ci
) periods
WHERE d.dept_code IN ('DEPT_IM','DEPT_GS','DEPT_PED','DEPT_OB','DEPT_ORT','DEPT_DERM','DEPT_OPH','DEPT_ENT')
  AND NOT EXISTS (
    SELECT 1 FROM schedule x
    WHERE x.staff_id = st.id
      AND x.work_date = days.work_date
      AND x.time_period = periods.p
  );

INSERT INTO schedule (dept_id, staff_id, work_date, time_period, total_count, remaining_count, register_fee)
SELECT st.dept_id, st.id, days.work_date, CONVERT(UNHEX('E6999AE4B88A') USING utf8mb4) COLLATE utf8mb4_unicode_ci, 10, 10, 50.00
FROM staff st
JOIN (
  WITH RECURSIVE days AS (
    SELECT DATE('2026-09-19') AS work_date
    UNION ALL
    SELECT DATE_ADD(work_date, INTERVAL 1 DAY) FROM days WHERE work_date < DATE('2026-10-19')
  )
  SELECT work_date FROM days
) days
WHERE st.staff_no = 'D001'
  AND NOT EXISTS (
    SELECT 1 FROM schedule x
    WHERE x.staff_id = st.id
      AND x.work_date = days.work_date
      AND x.time_period = CONVERT(UNHEX('E6999AE4B88A') USING utf8mb4) COLLATE utf8mb4_unicode_ci
  );

-- ---------------------------------------------------------------------------
-- 账号与患者授权：现有 patient.user_id 视为 SELF 主账号
-- ---------------------------------------------------------------------------
INSERT INTO user_patient_relation (user_id, patient_id, relation_type, is_default, status)
SELECT p.user_id, p.id, 'SELF', 1, 1
FROM patient p
WHERE p.user_id IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM user_patient_relation r
    WHERE r.user_id = p.user_id AND r.patient_id = p.id
  );

-- ---------------------------------------------------------------------------
-- 健康指标纵向记录：给每位已有档案的患者写入可画趋势的样例
-- BMI 不落库；身高仍在 patient_health_profile
-- ---------------------------------------------------------------------------
INSERT INTO health_metric_record (
  patient_id, created_by_user_id, metric_type, primary_value, secondary_value, measure_context, source_type, measured_at
)
SELECT p.id, p.user_id, v.metric_type, v.primary_value, v.secondary_value, v.measure_context, 'MANUAL', v.measured_at
FROM patient p
JOIN (
  SELECT 'WEIGHT' metric_type, 109.200 primary_value, CAST(NULL AS DECIMAL(10,3)) secondary_value, CAST(NULL AS CHAR(32)) measure_context, '2026-08-22 08:00:00' measured_at UNION ALL
  SELECT 'WEIGHT', 108.400, NULL, NULL, '2026-08-27 08:00:00' UNION ALL
  SELECT 'WEIGHT', 107.800, NULL, NULL, '2026-09-01 08:00:00' UNION ALL
  SELECT 'WEIGHT', 106.900, NULL, NULL, '2026-09-05 08:00:00' UNION ALL
  SELECT 'WEIGHT', 105.800, NULL, NULL, '2026-09-10 08:00:00' UNION ALL
  SELECT 'WEIGHT', 104.700, NULL, NULL, '2026-09-14 08:00:00' UNION ALL
  SELECT 'WEIGHT', 103.900, NULL, NULL, '2026-09-19 08:00:00' UNION ALL
  SELECT 'WAIST', 118.000, NULL, NULL, '2026-08-22 08:10:00' UNION ALL
  SELECT 'WAIST', 116.000, NULL, NULL, '2026-09-01 08:10:00' UNION ALL
  SELECT 'WAIST', 114.000, NULL, NULL, '2026-09-10 08:10:00' UNION ALL
  SELECT 'WAIST', 112.000, NULL, NULL, '2026-09-19 08:10:00' UNION ALL
  SELECT 'BLOOD_PRESSURE', 132.000, 86.000, NULL, '2026-09-01 08:20:00' UNION ALL
  SELECT 'BLOOD_PRESSURE', 128.000, 84.000, NULL, '2026-09-05 08:20:00' UNION ALL
  SELECT 'BLOOD_PRESSURE', 126.000, 82.000, NULL, '2026-09-10 08:20:00' UNION ALL
  SELECT 'BLOOD_PRESSURE', 124.000, 80.000, NULL, '2026-09-14 08:20:00' UNION ALL
  SELECT 'BLOOD_PRESSURE', 122.000, 78.000, NULL, '2026-09-19 08:20:00' UNION ALL
  SELECT 'BLOOD_GLUCOSE', 5.800, NULL, 'FASTING', '2026-09-01 07:30:00' UNION ALL
  SELECT 'BLOOD_GLUCOSE', 5.500, NULL, 'FASTING', '2026-09-05 07:30:00' UNION ALL
  SELECT 'BLOOD_GLUCOSE', 5.600, NULL, 'FASTING', '2026-09-10 07:30:00' UNION ALL
  SELECT 'BLOOD_GLUCOSE', 5.200, NULL, 'FASTING', '2026-09-14 07:30:00' UNION ALL
  SELECT 'BLOOD_GLUCOSE', 5.300, NULL, 'FASTING', '2026-09-19 07:30:00' UNION ALL
  SELECT 'HEART_RATE', 82.000, NULL, NULL, '2026-09-01 08:30:00' UNION ALL
  SELECT 'HEART_RATE', 80.000, NULL, NULL, '2026-09-05 08:30:00' UNION ALL
  SELECT 'HEART_RATE', 78.000, NULL, NULL, '2026-09-10 08:30:00' UNION ALL
  SELECT 'HEART_RATE', 76.000, NULL, NULL, '2026-09-14 08:30:00' UNION ALL
  SELECT 'HEART_RATE', 75.000, NULL, NULL, '2026-09-19 08:30:00' UNION ALL
  SELECT 'SPO2', 97.000, NULL, NULL, '2026-09-01 08:40:00' UNION ALL
  SELECT 'SPO2', 98.000, NULL, NULL, '2026-09-05 08:40:00' UNION ALL
  SELECT 'SPO2', 98.000, NULL, NULL, '2026-09-10 08:40:00' UNION ALL
  SELECT 'SPO2', 99.000, NULL, NULL, '2026-09-14 08:40:00' UNION ALL
  SELECT 'SPO2', 98.000, NULL, NULL, '2026-09-19 08:40:00' UNION ALL
  SELECT 'TEMPERATURE', 36.500, NULL, NULL, '2026-09-01 08:50:00' UNION ALL
  SELECT 'TEMPERATURE', 36.700, NULL, NULL, '2026-09-05 08:50:00' UNION ALL
  SELECT 'TEMPERATURE', 36.400, NULL, NULL, '2026-09-10 08:50:00' UNION ALL
  SELECT 'TEMPERATURE', 36.600, NULL, NULL, '2026-09-14 08:50:00' UNION ALL
  SELECT 'TEMPERATURE', 36.500, NULL, NULL, '2026-09-19 08:50:00'
) v
WHERE NOT EXISTS (
    SELECT 1 FROM health_metric_record r
    WHERE r.patient_id = p.id
      AND r.metric_type = v.metric_type
      AND r.measured_at = v.measured_at
      AND r.is_deleted = 0
  );
