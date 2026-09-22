-- 加固账号—患者授权与 AI 患者隔离。
-- 适用前提：已执行 2026-09-19-user-patient-subject.sql。
-- 执行前必须备份，并先确认下面四组异常查询均返回 0 行。

USE wenrun;

SET NAMES utf8mb4;

SELECT DATABASE() AS target_database, VERSION() AS mysql_version;

-- 1. 关系枚举、布尔值或停用默认关系异常。
SELECT id, user_id, patient_id, relation_type, is_default, status
FROM user_patient_relation
WHERE relation_type NOT IN ('SELF', 'SPOUSE', 'CHILD', 'PARENT', 'OTHER')
   OR is_default NOT IN (0, 1)
   OR status NOT IN (0, 1)
   OR (status = 0 AND is_default = 1);

-- 2. 同一账号存在多个有效默认患者。
SELECT user_id, COUNT(*) AS default_count
FROM user_patient_relation
WHERE status = 1 AND is_default = 1
GROUP BY user_id
HAVING COUNT(*) > 1;

-- 3. 同一账号存在多个有效 SELF 患者。
SELECT user_id, COUNT(*) AS self_count
FROM user_patient_relation
WHERE status = 1 AND relation_type = 'SELF'
GROUP BY user_id
HAVING COUNT(*) > 1;

-- 4. 仍未绑定患者的历史 AI 会话。
SELECT user_id, conversation_id
FROM ai_conversations
WHERE patient_id IS NULL;

-- MySQL 的 UNIQUE 允许多个 NULL，因此生成列只对“有效默认/SELF”行产生 user_id，
-- 其余行保持 NULL，从而在数据库层保证每个账号最多一个有效默认患者和一个有效本人患者。
ALTER TABLE user_patient_relation
  ADD COLUMN active_default_user_id BIGINT GENERATED ALWAYS AS (
    CASE WHEN status = 1 AND is_default = 1 THEN user_id ELSE NULL END
  ) STORED COMMENT '用于保证每个账号至多一个有效默认患者' AFTER status,
  ADD COLUMN active_self_user_id BIGINT GENERATED ALWAYS AS (
    CASE WHEN status = 1 AND relation_type = 'SELF' THEN user_id ELSE NULL END
  ) STORED COMMENT '用于保证每个账号至多一个有效本人患者' AFTER active_default_user_id,
  ADD UNIQUE KEY uk_user_patient_active_default (active_default_user_id),
  ADD UNIQUE KEY uk_user_patient_active_self (active_self_user_id),
  ADD KEY idx_user_patient_active_list (user_id, status, is_default, id),
  ADD KEY idx_patient_user_active (patient_id, status, user_id),
  ADD CONSTRAINT chk_user_patient_relation_type
    CHECK (relation_type IN ('SELF', 'SPOUSE', 'CHILD', 'PARENT', 'OTHER')),
  ADD CONSTRAINT chk_user_patient_is_default CHECK (is_default IN (0, 1)),
  ADD CONSTRAINT chk_user_patient_status CHECK (status IN (0, 1)),
  ADD CONSTRAINT chk_user_patient_inactive_not_default CHECK (status = 1 OR is_default = 0),
  DROP INDEX idx_user_patient_user_id,
  DROP INDEX idx_user_patient_patient_id;

-- 当前 Java 在创建/恢复会话前都会解析并校验 patient_id；数据库同步收紧为非空。
ALTER TABLE ai_conversations
  MODIFY COLUMN patient_id BIGINT NOT NULL
    COMMENT '当前会话讨论的患者ID，对应 patient.id；会话内不可切换',
  ADD KEY idx_ai_conversations_user_patient_update (user_id, patient_id, update_time);

-- 执行后核验。
SHOW CREATE TABLE user_patient_relation;
SHOW CREATE TABLE ai_conversations;
