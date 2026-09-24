-- 运动与睡眠手动记录。归属 patient_id，录入人 created_by_user_id。
-- 睡眠时长由入睡、醒来时间计算后落库，列表按发生时间排序，支持补录。

USE wenrun;

SET NAMES utf8mb4;

SELECT DATABASE() AS target_database;

CREATE TABLE IF NOT EXISTS patient_exercise_record (
  id                  BIGINT         NOT NULL AUTO_INCREMENT COMMENT '主键',
  patient_id          BIGINT         NOT NULL COMMENT '患者ID，对应 patient.id',
  exercise_type       VARCHAR(32)    NOT NULL COMMENT 'WALK/RUN/CYCLE/SWIM/STRENGTH/YOGA/BALL/OTHER',
  duration_min        INT            NOT NULL COMMENT '运动时长，分钟',
  distance_km         DECIMAL(6, 2)  DEFAULT NULL COMMENT '距离公里，可空',
  calories_kcal       INT            DEFAULT NULL COMMENT '消耗热量千卡，可空',
  intensity           VARCHAR(16)    DEFAULT NULL COMMENT 'LOW/MODERATE/HIGH，可空',
  source_type         VARCHAR(32)    NOT NULL DEFAULT 'MANUAL' COMMENT 'MANUAL/DEVICE/HOSPITAL/REPORT/AI_EXTRACT',
  started_at          DATETIME       NOT NULL COMMENT '运动开始时间',
  created_by_user_id  BIGINT         DEFAULT NULL COMMENT '录入人账号ID，对应 sys_user.id',
  remark              VARCHAR(255)   DEFAULT NULL COMMENT '备注',
  created_at          DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '写入时间',
  updated_at          DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  is_deleted          TINYINT        NOT NULL DEFAULT 0 COMMENT '0正常 1逻辑删除',
  PRIMARY KEY (id),
  KEY idx_exercise_patient_time (patient_id, started_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='患者运动记录；归属患者 patient_id';

CREATE TABLE IF NOT EXISTS patient_sleep_record (
  id                  BIGINT         NOT NULL AUTO_INCREMENT COMMENT '主键',
  patient_id          BIGINT         NOT NULL COMMENT '患者ID，对应 patient.id',
  bedtime             DATETIME       NOT NULL COMMENT '入睡时间',
  wake_time           DATETIME       NOT NULL COMMENT '醒来时间',
  duration_min        INT            NOT NULL COMMENT '睡眠时长分钟，由入睡与醒来时间计算',
  quality             TINYINT        NOT NULL COMMENT '睡眠质量 1很差 2较差 3一般 4较好 5很好',
  source_type         VARCHAR(32)    NOT NULL DEFAULT 'MANUAL' COMMENT 'MANUAL/DEVICE/HOSPITAL/REPORT/AI_EXTRACT',
  created_by_user_id  BIGINT         DEFAULT NULL COMMENT '录入人账号ID，对应 sys_user.id',
  remark              VARCHAR(255)   DEFAULT NULL COMMENT '备注',
  created_at          DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '写入时间',
  updated_at          DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  is_deleted          TINYINT        NOT NULL DEFAULT 0 COMMENT '0正常 1逻辑删除',
  PRIMARY KEY (id),
  KEY idx_sleep_patient_wake (patient_id, wake_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='患者睡眠记录；归属患者 patient_id';
