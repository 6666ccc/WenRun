-- 患者就医资料：一份一行，COS/OSS 稳定 URL 存在 files_json。
-- 归属 patient_id；uploaded_by_user_id 是上传人，不是资料主人。
-- 不关联 registration。

USE wenrun;

SET NAMES utf8mb4;

SELECT DATABASE() AS target_database;

CREATE TABLE IF NOT EXISTS patient_medical_document (
  id                   BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
  patient_id           BIGINT       NOT NULL COMMENT '患者ID，对应 patient.id',
  doc_type             VARCHAR(32)  NOT NULL COMMENT 'MEDICAL_RECORD/LAB_REPORT/MEDICATION/CHECKUP',
  title                VARCHAR(128) DEFAULT NULL COMMENT '标题，可空',
  occurred_at          DATETIME     DEFAULT NULL COMMENT '检查或资料发生时间；列表优先按此排序',
  files_json           JSON         NOT NULL COMMENT '文件数组，至少 1 项；url 为去 query 的稳定地址',
  uploaded_by_user_id  BIGINT       NOT NULL COMMENT '上传人账号ID，对应 sys_user.id；不是资料主人',
  created_at           DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '写入时间',
  updated_at           DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  is_deleted           TINYINT      NOT NULL DEFAULT 0 COMMENT '0正常 1逻辑删除',
  PRIMARY KEY (id),
  KEY idx_med_doc_patient_type_time (patient_id, doc_type, occurred_at),
  KEY idx_med_doc_patient_created (patient_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='患者就医资料；一份一行，文件地址在 files_json';
