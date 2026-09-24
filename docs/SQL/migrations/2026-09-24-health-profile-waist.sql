-- 健康档案当前值/快照补齐腰围，与趋势表 health_metric_record.WAIST 对齐。
-- 腰高比不落库，由腰围和身高计算。

USE wenrun;

SET NAMES utf8mb4;

SELECT DATABASE() AS target_database;

SET @sql = (
  SELECT IF(
    COUNT(*) = 0,
    'ALTER TABLE patient_health_profile ADD COLUMN waist_cm DECIMAL(5, 1) DEFAULT NULL COMMENT ''腰围cm'' AFTER weight_kg',
    'SELECT ''patient_health_profile.waist_cm exists'' AS skipped'
  )
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'patient_health_profile'
    AND COLUMN_NAME = 'waist_cm'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = (
  SELECT IF(
    COUNT(*) = 0,
    'ALTER TABLE patient_health_snapshot ADD COLUMN waist_cm DECIMAL(5, 1) DEFAULT NULL COMMENT ''腰围cm'' AFTER weight_kg',
    'SELECT ''patient_health_snapshot.waist_cm exists'' AS skipped'
  )
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'patient_health_snapshot'
    AND COLUMN_NAME = 'waist_cm'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
