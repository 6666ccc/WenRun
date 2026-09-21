-- 历史建表脚本。指标归属已改为 patient_id，请以 schema.sql
-- 与 2026-09-19-user-patient-subject.sql 为准。本文件仅保留为
-- 已执行环境的幂等 CREATE IF NOT EXISTS，新列定义与当前模型一致。
-- 身高仍在 patient_health_profile.height_cm；BMI 不落库，由身高 + 体重历史动态计算。
-- 趋势图必须按 measured_at 排序，不能按 created_at（支持补录历史数据）。

USE wenrun;

SET NAMES utf8mb4;

SELECT DATABASE() AS target_database;

CREATE TABLE IF NOT EXISTS health_metric_record (
  id                  BIGINT         NOT NULL AUTO_INCREMENT COMMENT '主键',
  patient_id          BIGINT         NOT NULL COMMENT '患者ID，对应 patient.id',
  metric_type         VARCHAR(32)    NOT NULL COMMENT '指标类型英文枚举，如 WEIGHT/BLOOD_PRESSURE',
  primary_value       DECIMAL(10, 3) NOT NULL COMMENT '主要指标值；血压为收缩压',
  secondary_value     DECIMAL(10, 3) DEFAULT NULL COMMENT '第二指标值；血压为舒张压',
  measure_context     VARCHAR(32)    DEFAULT NULL COMMENT '测量场景，主要用于血糖 FASTING/BEFORE_MEAL 等',
  source_type         VARCHAR(32)    NOT NULL DEFAULT 'MANUAL' COMMENT '数据来源：MANUAL/DEVICE/HOSPITAL/REPORT/AI_EXTRACT',
  measured_at         DATETIME       NOT NULL COMMENT '实际测量时间，趋势图按此排序',
  created_by_user_id  BIGINT         DEFAULT NULL COMMENT '录入人账号ID，对应 sys_user.id',
  remark              VARCHAR(255)   DEFAULT NULL COMMENT '备注',
  created_at          DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '记录写入数据库的时间',
  updated_at          DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  is_deleted          TINYINT        NOT NULL DEFAULT 0 COMMENT '0正常 1逻辑删除',
  PRIMARY KEY (id),
  KEY idx_health_metric_patient_type_time (patient_id, metric_type, measured_at),
  KEY idx_health_metric_patient_time (patient_id, measured_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='健康指标纵向记录；归属患者 patient_id，录入人 created_by_user_id';
