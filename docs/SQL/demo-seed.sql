-- WenRun 演示虚拟数据（可重复执行）
-- 演示账号密码与管理员相同：liu123456789
-- 不改动已有管理员 liuchang、患者 lc，以及 chat_messages

USE wenrun;
SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci;

SET @demo_pwd := '$2b$10$S4y2pi5jMKm.yjfWEVaNbO4PBIvkssjlfnyycjqi/6M6O3.Y9dPm2';

-- ---------------------------------------------------------------------------
-- 科室
-- ---------------------------------------------------------------------------
INSERT INTO dept (dept_code, dept_name, parent_id, status) VALUES
  ('DEPT_IM',    '内科',     NULL, 1),
  ('DEPT_GS',    '外科',     NULL, 1),
  ('DEPT_PED',   '儿科',     NULL, 1),
  ('DEPT_OB',    '妇产科',   NULL, 1),
  ('DEPT_ORT',   '骨科',     NULL, 1),
  ('DEPT_DERM',  '皮肤科',   NULL, 1),
  ('DEPT_OPH',   '眼科',     NULL, 1),
  ('DEPT_ENT',   '耳鼻喉科', NULL, 1),
  ('DEPT_LAB',   '检验科',   NULL, 1),
  ('DEPT_RAD',   '放射科',   NULL, 1),
  ('DEPT_PHARM', '药房',     NULL, 1),
  ('DEPT_CASH',  '收费处',   NULL, 1)
ON DUPLICATE KEY UPDATE
  dept_name = VALUES(dept_name),
  status = VALUES(status);

-- ---------------------------------------------------------------------------
-- 演示账号（医生 / 收费 / 药师 / 患者）
-- ---------------------------------------------------------------------------
INSERT INTO sys_user (username, password, real_name, phone, phone_verified, account_type, status) VALUES
  ('doctor1',     @demo_pwd, '张伟', '13800001001', 1, 'staff',   1),
  ('doctor2',     @demo_pwd, '李娜', '13800001002', 1, 'staff',   1),
  ('doctor3',     @demo_pwd, '王强', '13800001003', 1, 'staff',   1),
  ('doctor4',     @demo_pwd, '赵敏', '13800001004', 1, 'staff',   1),
  ('doctor5',     @demo_pwd, '陈静', '13800001005', 1, 'staff',   1),
  ('doctor6',     @demo_pwd, '刘洋', '13800001006', 1, 'staff',   1),
  ('doctor7',     @demo_pwd, '周芳', '13800001007', 1, 'staff',   1),
  ('doctor8',     @demo_pwd, '吴磊', '13800001008', 1, 'staff',   1),
  ('doctor9',     @demo_pwd, '郑凯', '13800001009', 1, 'staff',   1),
  ('cashier1',    @demo_pwd, '孙丽', '13800002001', 1, 'staff',   1),
  ('pharmacist1', @demo_pwd, '马超', '13800003001', 1, 'staff',   1),
  ('wangfang',    @demo_pwd, '王芳', '13900004001', 1, 'patient', 1),
  ('zhangming',   @demo_pwd, '张明', '13900004002', 1, 'patient', 1),
  ('lixia',       @demo_pwd, '李霞', '13900004003', 1, 'patient', 1),
  ('chenhao',     @demo_pwd, '陈浩', '13900004004', 1, 'patient', 1)
ON DUPLICATE KEY UPDATE
  password = VALUES(password),
  real_name = VALUES(real_name),
  phone = VALUES(phone),
  phone_verified = VALUES(phone_verified),
  account_type = VALUES(account_type),
  status = VALUES(status);

INSERT IGNORE INTO sys_user_role (user_id, role_id)
SELECT u.id, r.id FROM sys_user u JOIN sys_role r ON r.role_code = 'doctor' WHERE u.username IN ('doctor1','doctor2','doctor3','doctor4','doctor5','doctor6','doctor7','doctor8','doctor9');

INSERT IGNORE INTO sys_user_role (user_id, role_id)
SELECT u.id, r.id FROM sys_user u JOIN sys_role r ON r.role_code = 'cashier' WHERE u.username = 'cashier1';

INSERT IGNORE INTO sys_user_role (user_id, role_id)
SELECT u.id, r.id FROM sys_user u JOIN sys_role r ON r.role_code = 'pharmacist' WHERE u.username = 'pharmacist1';

INSERT IGNORE INTO sys_user_role (user_id, role_id)
SELECT u.id, r.id FROM sys_user u JOIN sys_role r ON r.role_code = 'patient' WHERE u.username IN ('wangfang','zhangming','lixia','chenhao');

-- ---------------------------------------------------------------------------
-- 医护
-- ---------------------------------------------------------------------------
INSERT INTO staff (staff_no, name, dept_id, title, user_id, status)
SELECT v.staff_no, v.name, d.id, v.title, u.id, 1
FROM (
  SELECT 'D001' staff_no, '张伟' name, 'DEPT_IM' dept_code, '主任医师' title, 'doctor1' username UNION ALL
  SELECT 'D002', '李娜', 'DEPT_IM', '主治医师', 'doctor2' UNION ALL
  SELECT 'D003', '王强', 'DEPT_GS', '主任医师', 'doctor3' UNION ALL
  SELECT 'D004', '赵敏', 'DEPT_PED', '主治医师', 'doctor4' UNION ALL
  SELECT 'D005', '陈静', 'DEPT_OB', '副主任医师', 'doctor5' UNION ALL
  SELECT 'D006', '刘洋', 'DEPT_ORT', '主治医师', 'doctor6' UNION ALL
  SELECT 'D007', '周芳', 'DEPT_DERM', '主治医师', 'doctor7' UNION ALL
  SELECT 'D008', '吴磊', 'DEPT_OPH', '主治医师', 'doctor8' UNION ALL
  SELECT 'D009', '郑凯', 'DEPT_ENT', '主治医师', 'doctor9' UNION ALL
  SELECT 'C001', '孙丽', 'DEPT_CASH', '收费员', 'cashier1' UNION ALL
  SELECT 'P001', '马超', 'DEPT_PHARM', '主管药师', 'pharmacist1'
) v
JOIN dept d ON d.dept_code = v.dept_code
JOIN sys_user u ON u.username = v.username
ON DUPLICATE KEY UPDATE
  name = VALUES(name),
  dept_id = VALUES(dept_id),
  title = VALUES(title),
  user_id = VALUES(user_id),
  status = VALUES(status);

-- ---------------------------------------------------------------------------
-- 患者档案（含已有 lc，以及两名无登录账号的现场患者）
-- ---------------------------------------------------------------------------
INSERT INTO patient (patient_no, name, gender, birth_date, id_card, phone, user_id, allergy_history, address)
SELECT v.patient_no, v.name, v.gender, v.birth_date, v.id_card, v.phone, u.id, v.allergy_history, v.address
FROM (
  SELECT 'PDEMO001' patient_no, '王芳' name, 0 gender, DATE('1988-03-12') birth_date, '110101198803120021' id_card, '13900004001' phone, 'wangfang' username, '青霉素过敏' allergy_history, '北京市朝阳区演示路 12 号' address UNION ALL
  SELECT 'PDEMO002', '张明', 1, DATE('1992-07-08'), '110101199207080033', '13900004002', 'zhangming', NULL, '北京市海淀区演示街 8 号' UNION ALL
  SELECT 'PDEMO003', '李霞', 0, DATE('1979-11-21'), '110101197911210046', '13900004003', 'lixia', '磺胺类过敏', '北京市西城区演示巷 3 号' UNION ALL
  SELECT 'PDEMO004', '陈浩', 1, DATE('2018-05-16'), '110101201805160019', '13900004004', 'chenhao', NULL, '北京市东城区演示里 5 号'
) v
JOIN sys_user u ON u.username = v.username
ON DUPLICATE KEY UPDATE
  name = VALUES(name),
  gender = VALUES(gender),
  birth_date = VALUES(birth_date),
  phone = VALUES(phone),
  user_id = VALUES(user_id),
  allergy_history = VALUES(allergy_history),
  address = VALUES(address);

INSERT INTO patient (patient_no, name, gender, birth_date, id_card, phone, user_id, allergy_history, address)
SELECT 'PDEMO005', '赵建国', 1, DATE('1956-02-03'), '110101195602030011', '13700005001', NULL, '阿司匹林过敏', '北京市丰台区演示南路 20 号'
WHERE NOT EXISTS (SELECT 1 FROM patient WHERE patient_no = 'PDEMO005');

INSERT INTO patient (patient_no, name, gender, birth_date, id_card, phone, user_id, allergy_history, address)
SELECT 'PDEMO006', '刘秀英', 0, DATE('1963-09-27'), '110101196309270028', '13700005002', NULL, NULL, '北京市通州区演示东街 9 号'
WHERE NOT EXISTS (SELECT 1 FROM patient WHERE patient_no = 'PDEMO006');

-- ---------------------------------------------------------------------------
-- 排班：临床医生 昨天到未来 6 天，上午/下午；张伟另加今晚/明晚
-- ---------------------------------------------------------------------------
INSERT INTO schedule (dept_id, staff_id, work_date, time_period, total_count, remaining_count, register_fee)
SELECT st.dept_id, st.id, DATE_ADD(CURDATE(), INTERVAL days.n DAY), periods.p, 20, 20,
  CASE st.title
    WHEN '主任医师' THEN 50.00
    WHEN '副主任医师' THEN 35.00
    WHEN '主治医师' THEN 25.00
    ELSE 15.00
  END
FROM staff st
JOIN dept d ON d.id = st.dept_id
JOIN (
  SELECT -1 AS n UNION ALL SELECT 0 UNION ALL SELECT 1 UNION ALL SELECT 2
  UNION ALL SELECT 3 UNION ALL SELECT 4 UNION ALL SELECT 5 UNION ALL SELECT 6
) days
JOIN (
  SELECT '上午' AS p UNION ALL SELECT '下午'
) periods
WHERE d.dept_code IN ('DEPT_IM','DEPT_GS','DEPT_PED','DEPT_OB','DEPT_ORT','DEPT_DERM','DEPT_OPH','DEPT_ENT')
  AND NOT EXISTS (
    SELECT 1 FROM schedule x
    WHERE x.staff_id = st.id
      AND x.work_date = DATE_ADD(CURDATE(), INTERVAL days.n DAY)
      AND x.time_period = periods.p
  );

INSERT INTO schedule (dept_id, staff_id, work_date, time_period, total_count, remaining_count, register_fee)
SELECT st.dept_id, st.id, DATE_ADD(CURDATE(), INTERVAL days.n DAY), '晚上', 10, 10, 50.00
FROM staff st
JOIN (
  SELECT 0 AS n UNION ALL SELECT 1
) days
WHERE st.staff_no = 'D001'
  AND NOT EXISTS (
    SELECT 1 FROM schedule x
    WHERE x.staff_id = st.id
      AND x.work_date = DATE_ADD(CURDATE(), INTERVAL days.n DAY)
      AND x.time_period = '晚上'
  );

-- ---------------------------------------------------------------------------
-- 药品与库存
-- ---------------------------------------------------------------------------
INSERT INTO drug (drug_code, drug_name, spec, unit, price, manufacturer, status) VALUES
  ('DRUG001', '阿莫西林胶囊', '0.25g×24粒', '盒', 18.60, '华北制药', 1),
  ('DRUG002', '布洛芬缓释胶囊', '0.3g×20粒', '盒', 16.80, '中美天津史克', 1),
  ('DRUG003', '对乙酰氨基酚片', '0.5g×12片', '盒', 8.50, '西南药业', 1),
  ('DRUG004', '氯雷他定片', '10mg×6片', '盒', 12.30, '拜耳医药', 1),
  ('DRUG005', '奥美拉唑肠溶胶囊', '20mg×14粒', '盒', 22.00, '阿斯利康', 1),
  ('DRUG006', '蒙脱石散', '3g×10袋', '盒', 15.40, '博福-益普生', 1),
  ('DRUG007', '氨溴索口服液', '100ml', '瓶', 19.80, '勃林格殷格翰', 1),
  ('DRUG008', '复方甘草片', '50片', '瓶', 6.50, '上海信谊', 1),
  ('DRUG009', '维生素C片', '0.1g×100片', '瓶', 9.90, '华中药业', 1),
  ('DRUG010', '硝苯地平缓释片', '10mg×30片', '盒', 28.00, '拜耳医药', 1),
  ('DRUG011', '头孢克肟胶囊', '0.1g×6粒', '盒', 32.50, '广州白云山', 1),
  ('DRUG012', '开塞露', '20ml', '支', 3.20, '天津药业', 1)
ON DUPLICATE KEY UPDATE
  drug_name = VALUES(drug_name),
  spec = VALUES(spec),
  unit = VALUES(unit),
  price = VALUES(price),
  manufacturer = VALUES(manufacturer),
  status = VALUES(status);

INSERT INTO drug_stock (drug_id, quantity, warn_quantity)
SELECT d.id, v.quantity, v.warn_quantity
FROM (
  SELECT 'DRUG001' code, 200.00 quantity, 50.00 warn_quantity UNION ALL
  SELECT 'DRUG002', 150.00, 30.00 UNION ALL
  SELECT 'DRUG003', 180.00, 40.00 UNION ALL
  SELECT 'DRUG004', 90.00, 20.00 UNION ALL
  SELECT 'DRUG005', 80.00, 20.00 UNION ALL
  SELECT 'DRUG006', 70.00, 15.00 UNION ALL
  SELECT 'DRUG007', 60.00, 15.00 UNION ALL
  SELECT 'DRUG008', 100.00, 20.00 UNION ALL
  SELECT 'DRUG009', 120.00, 30.00 UNION ALL
  SELECT 'DRUG010', 8.00, 20.00 UNION ALL
  SELECT 'DRUG011', 40.00, 10.00 UNION ALL
  SELECT 'DRUG012', 50.00, 10.00
) v
JOIN drug d ON d.drug_code = v.code
ON DUPLICATE KEY UPDATE
  quantity = VALUES(quantity),
  warn_quantity = VALUES(warn_quantity);

-- ---------------------------------------------------------------------------
-- 诊疗项目：1=影像检查 2=检验
-- ---------------------------------------------------------------------------
INSERT INTO medical_item (item_code, item_name, item_type, price, dept_id, status)
SELECT v.item_code, v.item_name, v.item_type, v.price, d.id, 1
FROM (
  SELECT 'ITEM001' item_code, '血常规' item_name, 2 item_type, 35.00 price, 'DEPT_LAB' dept_code UNION ALL
  SELECT 'ITEM002', 'C反应蛋白', 2, 45.00, 'DEPT_LAB' UNION ALL
  SELECT 'ITEM003', '尿常规', 2, 20.00, 'DEPT_LAB' UNION ALL
  SELECT 'ITEM004', '肝功能', 2, 55.00, 'DEPT_LAB' UNION ALL
  SELECT 'ITEM005', '空腹血糖', 2, 15.00, 'DEPT_LAB' UNION ALL
  SELECT 'ITEM006', '胸部X线', 1, 80.00, 'DEPT_RAD' UNION ALL
  SELECT 'ITEM007', '腹部B超', 1, 120.00, 'DEPT_RAD' UNION ALL
  SELECT 'ITEM008', '心电图', 1, 40.00, 'DEPT_IM'
) v
JOIN dept d ON d.dept_code = v.dept_code
ON DUPLICATE KEY UPDATE
  item_name = VALUES(item_name),
  item_type = VALUES(item_type),
  price = VALUES(price),
  dept_id = VALUES(dept_id),
  status = VALUES(status);

-- ---------------------------------------------------------------------------
-- 挂号：覆盖已挂号 / 已就诊 / 已退号，方便各门户演示
-- ---------------------------------------------------------------------------
INSERT INTO registration (reg_no, patient_id, schedule_id, dept_id, staff_id, reg_time, reg_fee, status, cashier_id, registrant_user_id)
SELECT 'REGDEMO-LC-FUTURE', p.id, sch.id, sch.dept_id, sch.staff_id,
       TIMESTAMP(DATE_ADD(CURDATE(), INTERVAL 1 DAY), '08:12:00'), sch.register_fee, 1,
       (SELECT id FROM sys_user WHERE username = 'cashier1'), p.user_id
FROM patient p
JOIN staff st ON st.staff_no = 'D001'
JOIN schedule sch ON sch.staff_id = st.id AND sch.work_date = DATE_ADD(CURDATE(), INTERVAL 1 DAY) AND sch.time_period = '上午'
WHERE p.patient_no = 'P202608181332177746'
  AND NOT EXISTS (SELECT 1 FROM registration x WHERE x.reg_no = 'REGDEMO-LC-FUTURE');

INSERT INTO registration (reg_no, patient_id, schedule_id, dept_id, staff_id, reg_time, reg_fee, status, cashier_id, registrant_user_id)
SELECT 'REGDEMO-LC-TODAY', p.id, sch.id, sch.dept_id, sch.staff_id,
       TIMESTAMP(CURDATE(), '08:05:00'), sch.register_fee, 2,
       (SELECT id FROM sys_user WHERE username = 'cashier1'), p.user_id
FROM patient p
JOIN staff st ON st.staff_no = 'D002'
JOIN schedule sch ON sch.staff_id = st.id AND sch.work_date = CURDATE() AND sch.time_period = '上午'
WHERE p.patient_no = 'P202608181332177746'
  AND NOT EXISTS (SELECT 1 FROM registration x WHERE x.reg_no = 'REGDEMO-LC-TODAY');

INSERT INTO registration (reg_no, patient_id, schedule_id, dept_id, staff_id, reg_time, reg_fee, status, cashier_id, registrant_user_id)
SELECT 'REGDEMO-LC-DONE', p.id, sch.id, sch.dept_id, sch.staff_id,
       TIMESTAMP(DATE_ADD(CURDATE(), INTERVAL -1 DAY), '08:20:00'), sch.register_fee, 2,
       (SELECT id FROM sys_user WHERE username = 'cashier1'), p.user_id
FROM patient p
JOIN staff st ON st.staff_no = 'D003'
JOIN schedule sch ON sch.staff_id = st.id AND sch.work_date = DATE_ADD(CURDATE(), INTERVAL -1 DAY) AND sch.time_period = '上午'
WHERE p.patient_no = 'P202608181332177746'
  AND NOT EXISTS (SELECT 1 FROM registration x WHERE x.reg_no = 'REGDEMO-LC-DONE');

INSERT INTO registration (reg_no, patient_id, schedule_id, dept_id, staff_id, reg_time, reg_fee, status, cashier_id, registrant_user_id)
SELECT 'REGDEMO-LC-CANCEL', p.id, sch.id, sch.dept_id, sch.staff_id,
       TIMESTAMP(DATE_ADD(CURDATE(), INTERVAL -1 DAY), '13:10:00'), sch.register_fee, 3,
       (SELECT id FROM sys_user WHERE username = 'cashier1'), p.user_id
FROM patient p
JOIN staff st ON st.staff_no = 'D004'
JOIN schedule sch ON sch.staff_id = st.id AND sch.work_date = DATE_ADD(CURDATE(), INTERVAL -1 DAY) AND sch.time_period = '下午'
WHERE p.patient_no = 'P202608181332177746'
  AND NOT EXISTS (SELECT 1 FROM registration x WHERE x.reg_no = 'REGDEMO-LC-CANCEL');

INSERT INTO registration (reg_no, patient_id, schedule_id, dept_id, staff_id, reg_time, reg_fee, status, cashier_id, registrant_user_id)
SELECT 'REGDEMO-WF-TODAY', p.id, sch.id, sch.dept_id, sch.staff_id,
       TIMESTAMP(CURDATE(), '08:18:00'), sch.register_fee, 2,
       (SELECT id FROM sys_user WHERE username = 'cashier1'), p.user_id
FROM patient p
JOIN staff st ON st.staff_no = 'D006'
JOIN schedule sch ON sch.staff_id = st.id AND sch.work_date = CURDATE() AND sch.time_period = '上午'
WHERE p.patient_no = 'PDEMO001'
  AND NOT EXISTS (SELECT 1 FROM registration x WHERE x.reg_no = 'REGDEMO-WF-TODAY');

INSERT INTO registration (reg_no, patient_id, schedule_id, dept_id, staff_id, reg_time, reg_fee, status, cashier_id, registrant_user_id)
SELECT 'REGDEMO-ZM-TODAY', p.id, sch.id, sch.dept_id, sch.staff_id,
       TIMESTAMP(CURDATE(), '08:32:00'), sch.register_fee, 2,
       (SELECT id FROM sys_user WHERE username = 'cashier1'), p.user_id
FROM patient p
JOIN staff st ON st.staff_no = 'D007'
JOIN schedule sch ON sch.staff_id = st.id AND sch.work_date = CURDATE() AND sch.time_period = '上午'
WHERE p.patient_no = 'PDEMO002'
  AND NOT EXISTS (SELECT 1 FROM registration x WHERE x.reg_no = 'REGDEMO-ZM-TODAY');

INSERT INTO registration (reg_no, patient_id, schedule_id, dept_id, staff_id, reg_time, reg_fee, status, cashier_id, registrant_user_id)
SELECT 'REGDEMO-LX-TODAY', p.id, sch.id, sch.dept_id, sch.staff_id,
       TIMESTAMP(CURDATE(), '09:05:00'), sch.register_fee, 2,
       (SELECT id FROM sys_user WHERE username = 'cashier1'), p.user_id
FROM patient p
JOIN staff st ON st.staff_no = 'D008'
JOIN schedule sch ON sch.staff_id = st.id AND sch.work_date = CURDATE() AND sch.time_period = '上午'
WHERE p.patient_no = 'PDEMO003'
  AND NOT EXISTS (SELECT 1 FROM registration x WHERE x.reg_no = 'REGDEMO-LX-TODAY');

INSERT INTO registration (reg_no, patient_id, schedule_id, dept_id, staff_id, reg_time, reg_fee, status, cashier_id, registrant_user_id)
SELECT 'REGDEMO-CH-TOM', p.id, sch.id, sch.dept_id, sch.staff_id,
       TIMESTAMP(CURDATE(), '10:40:00'), sch.register_fee, 1,
       (SELECT id FROM sys_user WHERE username = 'cashier1'), p.user_id
FROM patient p
JOIN staff st ON st.staff_no = 'D005'
JOIN schedule sch ON sch.staff_id = st.id AND sch.work_date = DATE_ADD(CURDATE(), INTERVAL 1 DAY) AND sch.time_period = '上午'
WHERE p.patient_no = 'PDEMO004'
  AND NOT EXISTS (SELECT 1 FROM registration x WHERE x.reg_no = 'REGDEMO-CH-TOM');

INSERT INTO registration (reg_no, patient_id, schedule_id, dept_id, staff_id, reg_time, reg_fee, status, cashier_id, registrant_user_id)
SELECT 'REGDEMO-ZJG-TODAY', p.id, sch.id, sch.dept_id, sch.staff_id,
       TIMESTAMP(CURDATE(), '09:28:00'), sch.register_fee, 2,
       (SELECT id FROM sys_user WHERE username = 'cashier1'), NULL
FROM patient p
JOIN staff st ON st.staff_no = 'D001'
JOIN schedule sch ON sch.staff_id = st.id AND sch.work_date = CURDATE() AND sch.time_period = '上午'
WHERE p.patient_no = 'PDEMO005'
  AND NOT EXISTS (SELECT 1 FROM registration x WHERE x.reg_no = 'REGDEMO-ZJG-TODAY');

-- 已挂号占用号源；退号不占用
UPDATE schedule s
JOIN (
  SELECT schedule_id, COUNT(*) AS used_cnt
  FROM registration
  WHERE status IN (1, 2)
  GROUP BY schedule_id
) x ON x.schedule_id = s.id
SET s.remaining_count = GREATEST(s.total_count - x.used_cnt, 0);

UPDATE schedule s
JOIN staff st ON st.id = s.staff_id AND st.staff_no = 'D001'
SET s.remaining_count = 0
WHERE s.work_date = CURDATE() AND s.time_period = '下午';

-- ---------------------------------------------------------------------------
-- 就诊
-- ---------------------------------------------------------------------------
INSERT INTO outpatient_visit (visit_no, registration_id, patient_id, staff_id, visit_time, chief_complaint, diagnosis, status)
SELECT 'VISITDEMO-LC-TODAY', r.id, r.patient_id, r.staff_id,
       TIMESTAMP(CURDATE(), '08:40:00'), '反复咳嗽一周，夜间加重', NULL, 1
FROM registration r
WHERE r.reg_no = 'REGDEMO-LC-TODAY'
  AND NOT EXISTS (SELECT 1 FROM outpatient_visit v WHERE v.visit_no = 'VISITDEMO-LC-TODAY');

INSERT INTO outpatient_visit (visit_no, registration_id, patient_id, staff_id, visit_time, chief_complaint, diagnosis, status)
SELECT 'VISITDEMO-LC-DONE', r.id, r.patient_id, r.staff_id,
       TIMESTAMP(DATE_ADD(CURDATE(), INTERVAL -1 DAY), '08:50:00'), '摔伤后左前臂疼痛肿胀', '左前臂软组织挫伤', 2
FROM registration r
WHERE r.reg_no = 'REGDEMO-LC-DONE'
  AND NOT EXISTS (SELECT 1 FROM outpatient_visit v WHERE v.visit_no = 'VISITDEMO-LC-DONE');

INSERT INTO outpatient_visit (visit_no, registration_id, patient_id, staff_id, visit_time, chief_complaint, diagnosis, status)
SELECT 'VISITDEMO-WF-TODAY', r.id, r.patient_id, r.staff_id,
       TIMESTAMP(CURDATE(), '08:45:00'), '腰部酸痛三天，久坐后加重', '腰肌劳损', 2
FROM registration r
WHERE r.reg_no = 'REGDEMO-WF-TODAY'
  AND NOT EXISTS (SELECT 1 FROM outpatient_visit v WHERE v.visit_no = 'VISITDEMO-WF-TODAY');

INSERT INTO outpatient_visit (visit_no, registration_id, patient_id, staff_id, visit_time, chief_complaint, diagnosis, status)
SELECT 'VISITDEMO-ZM-TODAY', r.id, r.patient_id, r.staff_id,
       TIMESTAMP(CURDATE(), '08:55:00'), '躯干散在风团伴瘙痒', '急性荨麻疹', 2
FROM registration r
WHERE r.reg_no = 'REGDEMO-ZM-TODAY'
  AND NOT EXISTS (SELECT 1 FROM outpatient_visit v WHERE v.visit_no = 'VISITDEMO-ZM-TODAY');

INSERT INTO outpatient_visit (visit_no, registration_id, patient_id, staff_id, visit_time, chief_complaint, diagnosis, status)
SELECT 'VISITDEMO-LX-TODAY', r.id, r.patient_id, r.staff_id,
       TIMESTAMP(CURDATE(), '09:20:00'), '用眼后视物模糊、眼干', '视疲劳', 2
FROM registration r
WHERE r.reg_no = 'REGDEMO-LX-TODAY'
  AND NOT EXISTS (SELECT 1 FROM outpatient_visit v WHERE v.visit_no = 'VISITDEMO-LX-TODAY');

INSERT INTO outpatient_visit (visit_no, registration_id, patient_id, staff_id, visit_time, chief_complaint, diagnosis, status)
SELECT 'VISITDEMO-ZJG-TODAY', r.id, r.patient_id, r.staff_id,
       TIMESTAMP(CURDATE(), '09:50:00'), '上腹烧灼感两周，空腹明显', '慢性胃炎？待查', 2
FROM registration r
WHERE r.reg_no = 'REGDEMO-ZJG-TODAY'
  AND NOT EXISTS (SELECT 1 FROM outpatient_visit v WHERE v.visit_no = 'VISITDEMO-ZJG-TODAY');

-- ---------------------------------------------------------------------------
-- 处方 / 明细
-- ---------------------------------------------------------------------------
INSERT INTO prescription (rx_no, visit_id, patient_id, staff_id, total_amount, status)
SELECT 'RXDEMO-LC-DONE', v.id, v.patient_id, v.staff_id, 26.70, 3
FROM outpatient_visit v
WHERE v.visit_no = 'VISITDEMO-LC-DONE'
  AND NOT EXISTS (SELECT 1 FROM prescription x WHERE x.rx_no = 'RXDEMO-LC-DONE');

INSERT INTO prescription (rx_no, visit_id, patient_id, staff_id, total_amount, status)
SELECT 'RXDEMO-WF-TODAY', v.id, v.patient_id, v.staff_id, 33.60, 2
FROM outpatient_visit v
WHERE v.visit_no = 'VISITDEMO-WF-TODAY'
  AND NOT EXISTS (SELECT 1 FROM prescription x WHERE x.rx_no = 'RXDEMO-WF-TODAY');

INSERT INTO prescription (rx_no, visit_id, patient_id, staff_id, total_amount, status)
SELECT 'RXDEMO-ZM-TODAY', v.id, v.patient_id, v.staff_id, 12.30, 3
FROM outpatient_visit v
WHERE v.visit_no = 'VISITDEMO-ZM-TODAY'
  AND NOT EXISTS (SELECT 1 FROM prescription x WHERE x.rx_no = 'RXDEMO-ZM-TODAY');

INSERT INTO prescription (rx_no, visit_id, patient_id, staff_id, total_amount, status)
SELECT 'RXDEMO-LX-TODAY', v.id, v.patient_id, v.staff_id, 9.90, 1
FROM outpatient_visit v
WHERE v.visit_no = 'VISITDEMO-LX-TODAY'
  AND NOT EXISTS (SELECT 1 FROM prescription x WHERE x.rx_no = 'RXDEMO-LX-TODAY');

INSERT INTO prescription (rx_no, visit_id, patient_id, staff_id, total_amount, status)
SELECT 'RXDEMO-ZJG-TODAY', v.id, v.patient_id, v.staff_id, 22.00, 2
FROM outpatient_visit v
WHERE v.visit_no = 'VISITDEMO-ZJG-TODAY'
  AND NOT EXISTS (SELECT 1 FROM prescription x WHERE x.rx_no = 'RXDEMO-ZJG-TODAY');

INSERT INTO prescription_item (prescription_id, drug_id, quantity, unit_price, amount, usage_desc)
SELECT rx.id, d.id, 1.00, d.price, d.price, '口服，一次 1 粒，一日 2 次，饭后服用'
FROM prescription rx JOIN drug d ON d.drug_code = 'DRUG002'
WHERE rx.rx_no = 'RXDEMO-LC-DONE'
  AND NOT EXISTS (SELECT 1 FROM prescription_item i WHERE i.prescription_id = rx.id AND i.drug_id = d.id);

INSERT INTO prescription_item (prescription_id, drug_id, quantity, unit_price, amount, usage_desc)
SELECT rx.id, d.id, 1.00, d.price, d.price, '口服，一次 1 片，一日 1 次'
FROM prescription rx JOIN drug d ON d.drug_code = 'DRUG009'
WHERE rx.rx_no = 'RXDEMO-LC-DONE'
  AND NOT EXISTS (SELECT 1 FROM prescription_item i WHERE i.prescription_id = rx.id AND i.drug_id = d.id);

INSERT INTO prescription_item (prescription_id, drug_id, quantity, unit_price, amount, usage_desc)
SELECT rx.id, d.id, 2.00, d.price, d.price * 2, '口服，一次 1 粒，一日 2 次，疼痛时服用'
FROM prescription rx JOIN drug d ON d.drug_code = 'DRUG002'
WHERE rx.rx_no = 'RXDEMO-WF-TODAY'
  AND NOT EXISTS (SELECT 1 FROM prescription_item i WHERE i.prescription_id = rx.id AND i.drug_id = d.id);

INSERT INTO prescription_item (prescription_id, drug_id, quantity, unit_price, amount, usage_desc)
SELECT rx.id, d.id, 1.00, d.price, d.price, '口服，一次 1 片，一日 1 次，睡前服用'
FROM prescription rx JOIN drug d ON d.drug_code = 'DRUG004'
WHERE rx.rx_no = 'RXDEMO-ZM-TODAY'
  AND NOT EXISTS (SELECT 1 FROM prescription_item i WHERE i.prescription_id = rx.id AND i.drug_id = d.id);

INSERT INTO prescription_item (prescription_id, drug_id, quantity, unit_price, amount, usage_desc)
SELECT rx.id, d.id, 1.00, d.price, d.price, '口服，一次 1 片，一日 1 次'
FROM prescription rx JOIN drug d ON d.drug_code = 'DRUG009'
WHERE rx.rx_no = 'RXDEMO-LX-TODAY'
  AND NOT EXISTS (SELECT 1 FROM prescription_item i WHERE i.prescription_id = rx.id AND i.drug_id = d.id);

INSERT INTO prescription_item (prescription_id, drug_id, quantity, unit_price, amount, usage_desc)
SELECT rx.id, d.id, 1.00, d.price, d.price, '口服，一次 1 粒，一日 1 次，晨起空腹'
FROM prescription rx JOIN drug d ON d.drug_code = 'DRUG005'
WHERE rx.rx_no = 'RXDEMO-ZJG-TODAY'
  AND NOT EXISTS (SELECT 1 FROM prescription_item i WHERE i.prescription_id = rx.id AND i.drug_id = d.id);

-- ---------------------------------------------------------------------------
-- 检查申请
-- ---------------------------------------------------------------------------
INSERT INTO exam_request (request_no, visit_id, patient_id, item_id, amount, status)
SELECT 'EXDEMO-LC-DONE', v.id, v.patient_id, i.id, i.price, 2
FROM outpatient_visit v
JOIN medical_item i ON i.item_code = 'ITEM001'
WHERE v.visit_no = 'VISITDEMO-LC-DONE'
  AND NOT EXISTS (SELECT 1 FROM exam_request x WHERE x.request_no = 'EXDEMO-LC-DONE');

INSERT INTO exam_request (request_no, visit_id, patient_id, item_id, amount, status)
SELECT 'EXDEMO-ZJG-TODAY', v.id, v.patient_id, i.id, i.price, 2
FROM outpatient_visit v
JOIN medical_item i ON i.item_code = 'ITEM007'
WHERE v.visit_no = 'VISITDEMO-ZJG-TODAY'
  AND NOT EXISTS (SELECT 1 FROM exam_request x WHERE x.request_no = 'EXDEMO-ZJG-TODAY');

INSERT INTO exam_request (request_no, visit_id, patient_id, item_id, amount, status)
SELECT 'EXDEMO-LX-TODAY', v.id, v.patient_id, i.id, i.price, 1
FROM outpatient_visit v
JOIN medical_item i ON i.item_code = 'ITEM008'
WHERE v.visit_no = 'VISITDEMO-LX-TODAY'
  AND NOT EXISTS (SELECT 1 FROM exam_request x WHERE x.request_no = 'EXDEMO-LX-TODAY');

-- ---------------------------------------------------------------------------
-- 发药（已发药处方）
-- ---------------------------------------------------------------------------
INSERT INTO dispense_record (prescription_id, pharmacist_id, dispense_time, status)
SELECT rx.id, (SELECT id FROM sys_user WHERE username = 'pharmacist1'),
       TIMESTAMP(DATE_ADD(CURDATE(), INTERVAL -1 DAY), '10:15:00'), 1
FROM prescription rx
WHERE rx.rx_no = 'RXDEMO-LC-DONE'
  AND NOT EXISTS (SELECT 1 FROM dispense_record d WHERE d.prescription_id = rx.id);

INSERT INTO dispense_record (prescription_id, pharmacist_id, dispense_time, status)
SELECT rx.id, (SELECT id FROM sys_user WHERE username = 'pharmacist1'),
       TIMESTAMP(CURDATE(), '09:40:00'), 1
FROM prescription rx
WHERE rx.rx_no = 'RXDEMO-ZM-TODAY'
  AND NOT EXISTS (SELECT 1 FROM dispense_record d WHERE d.prescription_id = rx.id);

-- ---------------------------------------------------------------------------
-- 收费单
-- ---------------------------------------------------------------------------
INSERT INTO charge_order (order_no, patient_id, visit_id, total_amount, paid_amount, pay_type, pay_status, cashier_id, pay_time)
SELECT 'CHGDEMO-LC-DONE', v.patient_id, v.id, 111.70, 111.70, 1, 1,
       (SELECT id FROM sys_user WHERE username = 'cashier1'),
       TIMESTAMP(DATE_ADD(CURDATE(), INTERVAL -1 DAY), '09:30:00')
FROM outpatient_visit v
WHERE v.visit_no = 'VISITDEMO-LC-DONE'
  AND NOT EXISTS (SELECT 1 FROM charge_order x WHERE x.order_no = 'CHGDEMO-LC-DONE');

INSERT INTO charge_order (order_no, patient_id, visit_id, total_amount, paid_amount, pay_type, pay_status, cashier_id, pay_time)
SELECT 'CHGDEMO-WF-TODAY', v.patient_id, v.id, 58.60, 58.60, 2, 1,
       (SELECT id FROM sys_user WHERE username = 'cashier1'),
       TIMESTAMP(CURDATE(), '09:10:00')
FROM outpatient_visit v
WHERE v.visit_no = 'VISITDEMO-WF-TODAY'
  AND NOT EXISTS (SELECT 1 FROM charge_order x WHERE x.order_no = 'CHGDEMO-WF-TODAY');

INSERT INTO charge_order (order_no, patient_id, visit_id, total_amount, paid_amount, pay_type, pay_status, cashier_id, pay_time)
SELECT 'CHGDEMO-ZM-TODAY', v.patient_id, v.id, 37.30, 37.30, 3, 1,
       (SELECT id FROM sys_user WHERE username = 'cashier1'),
       TIMESTAMP(CURDATE(), '09:20:00')
FROM outpatient_visit v
WHERE v.visit_no = 'VISITDEMO-ZM-TODAY'
  AND NOT EXISTS (SELECT 1 FROM charge_order x WHERE x.order_no = 'CHGDEMO-ZM-TODAY');

INSERT INTO charge_order (order_no, patient_id, visit_id, total_amount, paid_amount, pay_type, pay_status, cashier_id, pay_time)
SELECT 'CHGDEMO-ZJG-TODAY', v.patient_id, v.id, 192.00, 192.00, 4, 1,
       (SELECT id FROM sys_user WHERE username = 'cashier1'),
       TIMESTAMP(CURDATE(), '10:05:00')
FROM outpatient_visit v
WHERE v.visit_no = 'VISITDEMO-ZJG-TODAY'
  AND NOT EXISTS (SELECT 1 FROM charge_order x WHERE x.order_no = 'CHGDEMO-ZJG-TODAY');

INSERT INTO charge_order (order_no, patient_id, visit_id, total_amount, paid_amount, pay_type, pay_status, cashier_id, pay_time)
SELECT 'CHGDEMO-LX-TODAY', v.patient_id, v.id, 74.90, 0.00, NULL, 0,
       (SELECT id FROM sys_user WHERE username = 'cashier1'),
       NULL
FROM outpatient_visit v
WHERE v.visit_no = 'VISITDEMO-LX-TODAY'
  AND NOT EXISTS (SELECT 1 FROM charge_order x WHERE x.order_no = 'CHGDEMO-LX-TODAY');

INSERT INTO charge_detail (charge_order_id, biz_type, biz_id, item_name, amount)
SELECT o.id, 1, r.id, '挂号费', r.reg_fee
FROM charge_order o
JOIN outpatient_visit v ON v.id = o.visit_id
JOIN registration r ON r.id = v.registration_id
WHERE o.order_no = 'CHGDEMO-LC-DONE'
  AND NOT EXISTS (SELECT 1 FROM charge_detail d WHERE d.charge_order_id = o.id AND d.biz_type = 1);

INSERT INTO charge_detail (charge_order_id, biz_type, biz_id, item_name, amount)
SELECT o.id, 2, rx.id, '处方药品', rx.total_amount
FROM charge_order o
JOIN prescription rx ON rx.rx_no = 'RXDEMO-LC-DONE'
WHERE o.order_no = 'CHGDEMO-LC-DONE'
  AND NOT EXISTS (SELECT 1 FROM charge_detail d WHERE d.charge_order_id = o.id AND d.biz_type = 2);

INSERT INTO charge_detail (charge_order_id, biz_type, biz_id, item_name, amount)
SELECT o.id, 3, e.id, i.item_name, e.amount
FROM charge_order o
JOIN exam_request e ON e.request_no = 'EXDEMO-LC-DONE'
JOIN medical_item i ON i.id = e.item_id
WHERE o.order_no = 'CHGDEMO-LC-DONE'
  AND NOT EXISTS (SELECT 1 FROM charge_detail d WHERE d.charge_order_id = o.id AND d.biz_type = 3);

INSERT INTO charge_detail (charge_order_id, biz_type, biz_id, item_name, amount)
SELECT o.id, 1, r.id, '挂号费', r.reg_fee
FROM charge_order o
JOIN outpatient_visit v ON v.id = o.visit_id
JOIN registration r ON r.id = v.registration_id
WHERE o.order_no = 'CHGDEMO-WF-TODAY'
  AND NOT EXISTS (SELECT 1 FROM charge_detail d WHERE d.charge_order_id = o.id AND d.biz_type = 1);

INSERT INTO charge_detail (charge_order_id, biz_type, biz_id, item_name, amount)
SELECT o.id, 2, rx.id, '处方药品', rx.total_amount
FROM charge_order o
JOIN prescription rx ON rx.rx_no = 'RXDEMO-WF-TODAY'
WHERE o.order_no = 'CHGDEMO-WF-TODAY'
  AND NOT EXISTS (SELECT 1 FROM charge_detail d WHERE d.charge_order_id = o.id AND d.biz_type = 2);

INSERT INTO charge_detail (charge_order_id, biz_type, biz_id, item_name, amount)
SELECT o.id, 1, r.id, '挂号费', r.reg_fee
FROM charge_order o
JOIN outpatient_visit v ON v.id = o.visit_id
JOIN registration r ON r.id = v.registration_id
WHERE o.order_no = 'CHGDEMO-ZM-TODAY'
  AND NOT EXISTS (SELECT 1 FROM charge_detail d WHERE d.charge_order_id = o.id AND d.biz_type = 1);

INSERT INTO charge_detail (charge_order_id, biz_type, biz_id, item_name, amount)
SELECT o.id, 2, rx.id, '处方药品', rx.total_amount
FROM charge_order o
JOIN prescription rx ON rx.rx_no = 'RXDEMO-ZM-TODAY'
WHERE o.order_no = 'CHGDEMO-ZM-TODAY'
  AND NOT EXISTS (SELECT 1 FROM charge_detail d WHERE d.charge_order_id = o.id AND d.biz_type = 2);

INSERT INTO charge_detail (charge_order_id, biz_type, biz_id, item_name, amount)
SELECT o.id, 1, r.id, '挂号费', r.reg_fee
FROM charge_order o
JOIN outpatient_visit v ON v.id = o.visit_id
JOIN registration r ON r.id = v.registration_id
WHERE o.order_no = 'CHGDEMO-ZJG-TODAY'
  AND NOT EXISTS (SELECT 1 FROM charge_detail d WHERE d.charge_order_id = o.id AND d.biz_type = 1);

INSERT INTO charge_detail (charge_order_id, biz_type, biz_id, item_name, amount)
SELECT o.id, 2, rx.id, '处方药品', rx.total_amount
FROM charge_order o
JOIN prescription rx ON rx.rx_no = 'RXDEMO-ZJG-TODAY'
WHERE o.order_no = 'CHGDEMO-ZJG-TODAY'
  AND NOT EXISTS (SELECT 1 FROM charge_detail d WHERE d.charge_order_id = o.id AND d.biz_type = 2);

INSERT INTO charge_detail (charge_order_id, biz_type, biz_id, item_name, amount)
SELECT o.id, 3, e.id, i.item_name, e.amount
FROM charge_order o
JOIN exam_request e ON e.request_no = 'EXDEMO-ZJG-TODAY'
JOIN medical_item i ON i.id = e.item_id
WHERE o.order_no = 'CHGDEMO-ZJG-TODAY'
  AND NOT EXISTS (SELECT 1 FROM charge_detail d WHERE d.charge_order_id = o.id AND d.biz_type = 3);

INSERT INTO charge_detail (charge_order_id, biz_type, biz_id, item_name, amount)
SELECT o.id, 1, r.id, '挂号费', r.reg_fee
FROM charge_order o
JOIN outpatient_visit v ON v.id = o.visit_id
JOIN registration r ON r.id = v.registration_id
WHERE o.order_no = 'CHGDEMO-LX-TODAY'
  AND NOT EXISTS (SELECT 1 FROM charge_detail d WHERE d.charge_order_id = o.id AND d.biz_type = 1);

INSERT INTO charge_detail (charge_order_id, biz_type, biz_id, item_name, amount)
SELECT o.id, 2, rx.id, '处方药品', rx.total_amount
FROM charge_order o
JOIN prescription rx ON rx.rx_no = 'RXDEMO-LX-TODAY'
WHERE o.order_no = 'CHGDEMO-LX-TODAY'
  AND NOT EXISTS (SELECT 1 FROM charge_detail d WHERE d.charge_order_id = o.id AND d.biz_type = 2);

INSERT INTO charge_detail (charge_order_id, biz_type, biz_id, item_name, amount)
SELECT o.id, 3, e.id, i.item_name, e.amount
FROM charge_order o
JOIN exam_request e ON e.request_no = 'EXDEMO-LX-TODAY'
JOIN medical_item i ON i.id = e.item_id
WHERE o.order_no = 'CHGDEMO-LX-TODAY'
  AND NOT EXISTS (SELECT 1 FROM charge_detail d WHERE d.charge_order_id = o.id AND d.biz_type = 3);
