-- 健康档案当前值/快照补齐血氧、呼吸、体温，与趋势表 health_metric_record 对齐。

USE wenrun;

SET NAMES utf8mb4;

SELECT DATABASE() AS target_database;

SET @sql = (
  SELECT IF(
    COUNT(*) = 0,
    'ALTER TABLE patient_health_profile ADD COLUMN spo2_pct SMALLINT DEFAULT NULL COMMENT ''血氧%'' AFTER heart_rate_bpm, ADD COLUMN respiratory_rate_bpm SMALLINT DEFAULT NULL COMMENT ''呼吸频率次/分'' AFTER spo2_pct, ADD COLUMN temperature_c DECIMAL(4, 1) DEFAULT NULL COMMENT ''体温℃'' AFTER respiratory_rate_bpm',
    'SELECT ''patient_health_profile extra vitals exist'' AS skipped'
  )
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'patient_health_profile'
    AND COLUMN_NAME = 'spo2_pct'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = (
  SELECT IF(
    COUNT(*) = 0,
    'ALTER TABLE patient_health_snapshot ADD COLUMN spo2_pct SMALLINT DEFAULT NULL COMMENT ''血氧%'' AFTER heart_rate_bpm, ADD COLUMN respiratory_rate_bpm SMALLINT DEFAULT NULL COMMENT ''呼吸频率次/分'' AFTER spo2_pct, ADD COLUMN temperature_c DECIMAL(4, 1) DEFAULT NULL COMMENT ''体温℃'' AFTER respiratory_rate_bpm',
    'SELECT ''patient_health_snapshot extra vitals exist'' AS skipped'
  )
  FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'patient_health_snapshot'
    AND COLUMN_NAME = 'spo2_pct'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
