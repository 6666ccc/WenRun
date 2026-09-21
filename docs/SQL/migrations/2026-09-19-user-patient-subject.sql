-- 账号身份与患者医疗主体统一：
-- 1) 建立 user_patient_relation
-- 2) 将 health_metric_record.user_id 迁到 patient_id
-- 若历史数据存在“一个账号对应多个患者”或指标找不到患者，写入报告表后停止破坏性变更。

USE wenrun;

SET NAMES utf8mb4;

SELECT DATABASE() AS target_database;

CREATE TABLE IF NOT EXISTS user_patient_relation (
  id              BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
  user_id         BIGINT       NOT NULL COMMENT '登录账号ID，对应 sys_user.id',
  patient_id      BIGINT       NOT NULL COMMENT '患者ID，对应 patient.id',
  relation_type   VARCHAR(32)  NOT NULL COMMENT 'SELF/SPOUSE/CHILD/PARENT/OTHER',
  is_default      TINYINT      NOT NULL DEFAULT 0 COMMENT '是否为该账号当前默认患者',
  status          TINYINT      NOT NULL DEFAULT 1 COMMENT '1有效 0停用',
  created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  updated_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_user_patient (user_id, patient_id),
  KEY idx_user_patient_user_id (user_id),
  KEY idx_user_patient_patient_id (patient_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='账号与患者授权关系；授权只认此表';

INSERT INTO user_patient_relation (user_id, patient_id, relation_type, is_default, status)
SELECT p.user_id, p.id, 'SELF', 1, 1
FROM patient p
WHERE p.user_id IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM user_patient_relation r
    WHERE r.user_id = p.user_id AND r.patient_id = p.id
  );

CREATE TABLE IF NOT EXISTS _migration_identity_anomalies (
  kind        VARCHAR(64)  NOT NULL,
  user_id     BIGINT       DEFAULT NULL,
  patient_id  BIGINT       DEFAULT NULL,
  metric_id   BIGINT       DEFAULT NULL,
  detail      VARCHAR(255) DEFAULT NULL,
  created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='身份模型迁移异常，供人工确认，禁止静默覆盖';

DELETE FROM _migration_identity_anomalies;

INSERT INTO _migration_identity_anomalies (kind, user_id, detail)
SELECT 'USER_HAS_MULTIPLE_PATIENTS', p.user_id,
       CONCAT('patient_count=', COUNT(*))
FROM patient p
WHERE p.user_id IS NOT NULL
GROUP BY p.user_id
HAVING COUNT(*) > 1;

SET @sql = (
  SELECT IF(
    COUNT(*) = 0,
    'ALTER TABLE health_metric_record ADD COLUMN patient_id BIGINT NULL COMMENT ''患者ID，对应 patient.id'' AFTER id, ADD COLUMN created_by_user_id BIGINT NULL COMMENT ''录入人账号ID，对应 sys_user.id'' AFTER measured_at',
    'SELECT ''health_metric_record.patient_id exists'' AS skipped'
  )
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'health_metric_record'
    AND COLUMN_NAME = 'patient_id'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @has_metric_user_id = (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'health_metric_record'
    AND COLUMN_NAME = 'user_id'
);

SET @sql = IF(
  @has_metric_user_id > 0,
  'UPDATE health_metric_record h JOIN patient p ON p.user_id = h.user_id SET h.patient_id = p.id, h.created_by_user_id = IFNULL(h.created_by_user_id, h.user_id) WHERE h.patient_id IS NULL AND h.user_id IS NOT NULL AND (SELECT COUNT(*) FROM patient x WHERE x.user_id = h.user_id) = 1',
  'SELECT ''health_metric_record.user_id already removed'' AS skipped'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = IF(
  @has_metric_user_id > 0,
  'INSERT INTO _migration_identity_anomalies (kind, user_id, metric_id, detail) SELECT ''METRIC_WITHOUT_PATIENT'', h.user_id, h.id, ''health_metric_record.user_id has no patient'' FROM health_metric_record h LEFT JOIN patient p ON p.user_id = h.user_id WHERE h.patient_id IS NULL AND h.user_id IS NOT NULL AND p.id IS NULL',
  'SELECT ''skip METRIC_WITHOUT_PATIENT'' AS skipped'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = IF(
  @has_metric_user_id > 0,
  'INSERT INTO _migration_identity_anomalies (kind, user_id, metric_id, detail) SELECT ''METRIC_AMBIGUOUS_PATIENT'', h.user_id, h.id, ''user_id maps to multiple patients'' FROM health_metric_record h WHERE h.patient_id IS NULL AND h.user_id IS NOT NULL AND (SELECT COUNT(*) FROM patient x WHERE x.user_id = h.user_id) > 1',
  'SELECT ''skip METRIC_AMBIGUOUS_PATIENT'' AS skipped'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SELECT kind, user_id, patient_id, metric_id, detail
FROM _migration_identity_anomalies
ORDER BY kind, user_id, metric_id;

SET @anomaly_count = (SELECT COUNT(*) FROM _migration_identity_anomalies);
SET @has_user_id = (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'health_metric_record'
    AND COLUMN_NAME = 'user_id'
);
SET @nullable_patient_id = (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'health_metric_record'
    AND COLUMN_NAME = 'patient_id'
    AND IS_NULLABLE = 'YES'
);

SET @sql = IF(
  @anomaly_count = 0 AND @has_user_id > 0 AND @nullable_patient_id > 0,
  'ALTER TABLE health_metric_record MODIFY COLUMN patient_id BIGINT NOT NULL COMMENT ''患者ID，对应 patient.id'', DROP INDEX idx_health_metric_user_type_time, DROP INDEX idx_health_metric_user_time, DROP COLUMN user_id, ADD KEY idx_health_metric_patient_type_time (patient_id, metric_type, measured_at), ADD KEY idx_health_metric_patient_time (patient_id, measured_at)',
  'SELECT IF(@anomaly_count > 0, ''identity migration has anomalies; inspect _migration_identity_anomalies'', ''health_metric_record already migrated'') AS skipped'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SELECT IF(
  EXISTS (
    SELECT 1 FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'patient'
      AND COLUMN_NAME = 'user_id'
  ),
  'patient.user_id kept as creator/primary account; authorization uses user_patient_relation',
  'patient.user_id already removed'
) AS patient_user_id_status;
