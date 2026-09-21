-- 患者健康档案：当前值 + 每次保存的完整快照
-- 过敏史仍在 patient.allergy_history，本脚本不改动 patient 表。

USE wenrun;

SET NAMES utf8mb4;

SELECT DATABASE() AS target_database;

CREATE TABLE IF NOT EXISTS patient_health_profile (
  id                  BIGINT         NOT NULL AUTO_INCREMENT COMMENT '主键',
  patient_id          BIGINT         NOT NULL COMMENT '患者ID，对应 patient.id',
  height_cm           DECIMAL(5, 1)  DEFAULT NULL COMMENT '身高cm',
  weight_kg           DECIMAL(5, 1)  DEFAULT NULL COMMENT '体重kg',
  systolic_mmhg       SMALLINT       DEFAULT NULL COMMENT '收缩压mmHg',
  diastolic_mmhg      SMALLINT       DEFAULT NULL COMMENT '舒张压mmHg',
  glucose_mmol        DECIMAL(4, 1)  DEFAULT NULL COMMENT '血糖mmol/L',
  glucose_type        VARCHAR(24)    DEFAULT NULL COMMENT 'fasting空腹 / random随机 / postprandial餐后',
  heart_rate_bpm      SMALLINT       DEFAULT NULL COMMENT '心率次/分',
  measured_at         DATETIME       DEFAULT NULL COMMENT '上述体征最近一次测量时间',
  past_history        VARCHAR(2000)  DEFAULT NULL COMMENT '既往史',
  family_history      VARCHAR(2000)  DEFAULT NULL COMMENT '家族史',
  personal_history    VARCHAR(2000)  DEFAULT NULL COMMENT '个人史：烟酒、职业等',
  create_time         DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time         DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_patient_health_profile_patient (patient_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='患者健康档案当前值';

CREATE TABLE IF NOT EXISTS patient_health_snapshot (
  id                  BIGINT         NOT NULL AUTO_INCREMENT COMMENT '主键',
  patient_id          BIGINT         NOT NULL COMMENT '患者ID，对应 patient.id',
  height_cm           DECIMAL(5, 1)  DEFAULT NULL COMMENT '身高cm',
  weight_kg           DECIMAL(5, 1)  DEFAULT NULL COMMENT '体重kg',
  systolic_mmhg       SMALLINT       DEFAULT NULL COMMENT '收缩压mmHg',
  diastolic_mmhg      SMALLINT       DEFAULT NULL COMMENT '舒张压mmHg',
  glucose_mmol        DECIMAL(4, 1)  DEFAULT NULL COMMENT '血糖mmol/L',
  glucose_type        VARCHAR(24)    DEFAULT NULL COMMENT 'fasting空腹 / random随机 / postprandial餐后',
  heart_rate_bpm      SMALLINT       DEFAULT NULL COMMENT '心率次/分',
  measured_at         DATETIME       NOT NULL COMMENT '用户确认的测量/填写时间',
  past_history        VARCHAR(2000)  DEFAULT NULL COMMENT '既往史',
  family_history      VARCHAR(2000)  DEFAULT NULL COMMENT '家族史',
  personal_history    VARCHAR(2000)  DEFAULT NULL COMMENT '个人史',
  create_time         DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '系统写入时间',
  PRIMARY KEY (id),
  KEY idx_health_snapshot_patient_time (patient_id, measured_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='患者健康档案历史快照';
