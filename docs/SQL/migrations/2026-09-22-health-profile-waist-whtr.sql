-- 健康档案与快照补齐腰围，并由 MySQL 生成列维护 WHtR（腰围/身高）。
-- waist_cm 可写；whtr 只读，避免身高或腰围变化后派生值失去同步。

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
    'ALTER TABLE patient_health_profile ADD COLUMN whtr DECIMAL(5, 3) GENERATED ALWAYS AS (CASE WHEN height_cm > 0 AND waist_cm IS NOT NULL THEN ROUND(waist_cm / height_cm, 3) ELSE NULL END) STORED COMMENT ''腰围身高比，由腰围/身高自动计算'' AFTER waist_cm',
    'SELECT ''patient_health_profile.whtr exists'' AS skipped'
  )
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'patient_health_profile'
    AND COLUMN_NAME = 'whtr'
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

SET @sql = (
  SELECT IF(
    COUNT(*) = 0,
    'ALTER TABLE patient_health_snapshot ADD COLUMN whtr DECIMAL(5, 3) GENERATED ALWAYS AS (CASE WHEN height_cm > 0 AND waist_cm IS NOT NULL THEN ROUND(waist_cm / height_cm, 3) ELSE NULL END) STORED COMMENT ''腰围身高比，由腰围/身高自动计算'' AFTER waist_cm',
    'SELECT ''patient_health_snapshot.whtr exists'' AS skipped'
  )
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'patient_health_snapshot'
    AND COLUMN_NAME = 'whtr'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
