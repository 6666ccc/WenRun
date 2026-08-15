-- WenRun 门诊业务库建表脚本（由实体类 + MyBatis Mapper XML 复刻推断，非生产库导出）
-- 数据库: wenrun
-- 约定: InnoDB / utf8mb4；主键自增；不加外键；业务单号/编码加 UNIQUE；关联查询列加普通索引

CREATE DATABASE IF NOT EXISTS wenrun
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

USE wenrun;

SET NAMES utf8mb4;

-- ---------------------------------------------------------------------------
-- 1. 账号与权限
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS sys_user (
  id              BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
  username        VARCHAR(64)  NOT NULL COMMENT '登录名',
  password        VARCHAR(255) NOT NULL COMMENT '密码哈希',
  real_name       VARCHAR(64)  DEFAULT NULL COMMENT '真实姓名',
  phone           VARCHAR(20)  DEFAULT NULL COMMENT '手机号',
  phone_verified  TINYINT      NOT NULL DEFAULT 0 COMMENT '0未验证 1已验证',
  account_type    VARCHAR(32)  NOT NULL COMMENT 'internal/staff/patient',
  status          TINYINT      NOT NULL DEFAULT 1 COMMENT '账号状态',
  create_time     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_sys_user_username (username),
  KEY idx_sys_user_phone (phone),
  KEY idx_sys_user_account_type (account_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='系统用户';

CREATE TABLE IF NOT EXISTS sys_role (
  id              BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
  role_code       VARCHAR(64)  NOT NULL COMMENT '角色编码',
  role_name       VARCHAR(64)  NOT NULL COMMENT '角色名称',
  default_portal  VARCHAR(32)  DEFAULT NULL COMMENT '默认门户 admin/doctor/patient',
  create_time     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_sys_role_code (role_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='系统角色';

CREATE TABLE IF NOT EXISTS sys_user_role (
  user_id         BIGINT       NOT NULL COMMENT '用户ID',
  role_id         BIGINT       NOT NULL COMMENT '角色ID',
  PRIMARY KEY (user_id, role_id),
  KEY idx_sys_user_role_role_id (role_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户角色关联';

CREATE TABLE IF NOT EXISTS oauth_token_blacklist (
  jti             VARCHAR(64)  NOT NULL COMMENT 'JWT ID',
  expires_at      DATETIME     NOT NULL COMMENT '过期时间',
  PRIMARY KEY (jti),
  KEY idx_oauth_token_blacklist_expires_at (expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Token黑名单';

-- ---------------------------------------------------------------------------
-- 2. 组织与排班
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS dept (
  id              BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
  dept_code       VARCHAR(64)  NOT NULL COMMENT '科室编码',
  dept_name       VARCHAR(128) NOT NULL COMMENT '科室名称',
  parent_id       BIGINT       DEFAULT NULL COMMENT '上级科室ID',
  status          TINYINT      NOT NULL DEFAULT 1 COMMENT '状态',
  create_time     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_dept_code (dept_code),
  KEY idx_dept_parent_id (parent_id),
  KEY idx_dept_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='科室';

CREATE TABLE IF NOT EXISTS staff (
  id              BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
  staff_no        VARCHAR(64)  NOT NULL COMMENT '工号',
  name            VARCHAR(64)  NOT NULL COMMENT '姓名',
  dept_id         BIGINT       DEFAULT NULL COMMENT '科室ID',
  title           VARCHAR(64)  DEFAULT NULL COMMENT '职称',
  user_id         BIGINT       DEFAULT NULL COMMENT '绑定系统用户',
  status          TINYINT      NOT NULL DEFAULT 1 COMMENT '状态',
  create_time     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_staff_no (staff_no),
  KEY idx_staff_dept_id (dept_id),
  KEY idx_staff_user_id (user_id),
  KEY idx_staff_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='医护人员';

CREATE TABLE IF NOT EXISTS schedule (
  id              BIGINT         NOT NULL AUTO_INCREMENT COMMENT '主键',
  dept_id         BIGINT         NOT NULL COMMENT '科室ID',
  staff_id        BIGINT         NOT NULL COMMENT '医生ID',
  work_date       DATE           NOT NULL COMMENT '出诊日期',
  time_period     VARCHAR(32)    NOT NULL COMMENT '时段',
  total_count     INT            NOT NULL DEFAULT 0 COMMENT '总号源',
  remaining_count INT            NOT NULL DEFAULT 0 COMMENT '剩余号源',
  register_fee    DECIMAL(12, 2) NOT NULL DEFAULT 0.00 COMMENT '挂号费',
  create_time     DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time     DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  KEY idx_schedule_dept_id (dept_id),
  KEY idx_schedule_staff_id (staff_id),
  KEY idx_schedule_work_date (work_date),
  KEY idx_schedule_staff_date (staff_id, work_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='排班号源';

-- ---------------------------------------------------------------------------
-- 3. 患者与诊疗
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS patient (
  id              BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
  patient_no      VARCHAR(64)  NOT NULL COMMENT '患者编号',
  name            VARCHAR(64)  NOT NULL COMMENT '姓名',
  gender          TINYINT      DEFAULT NULL COMMENT '0女 1男 2未知',
  birth_date      DATE         DEFAULT NULL COMMENT '出生日期',
  id_card         VARCHAR(32)  DEFAULT NULL COMMENT '身份证号',
  phone           VARCHAR(20)  DEFAULT NULL COMMENT '手机号',
  user_id         BIGINT       DEFAULT NULL COMMENT '绑定患者端用户',
  allergy_history VARCHAR(500) DEFAULT NULL COMMENT '过敏史',
  address         VARCHAR(255) DEFAULT NULL COMMENT '地址',
  create_time     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_patient_no (patient_no),
  KEY idx_patient_phone (phone),
  KEY idx_patient_id_card (id_card),
  KEY idx_patient_user_id (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='患者';

CREATE TABLE IF NOT EXISTS registration (
  id                  BIGINT         NOT NULL AUTO_INCREMENT COMMENT '主键',
  reg_no              VARCHAR(64)    NOT NULL COMMENT '挂号单号',
  patient_id          BIGINT         NOT NULL COMMENT '患者ID',
  schedule_id         BIGINT         NOT NULL COMMENT '排班ID',
  dept_id             BIGINT         NOT NULL COMMENT '科室ID',
  staff_id            BIGINT         NOT NULL COMMENT '医生ID',
  reg_time            DATETIME       NOT NULL COMMENT '挂号时间',
  reg_fee             DECIMAL(12, 2) NOT NULL DEFAULT 0.00 COMMENT '挂号费',
  status              TINYINT        NOT NULL DEFAULT 0 COMMENT '挂号状态',
  cashier_id          BIGINT         DEFAULT NULL COMMENT '收银员ID',
  registrant_user_id  BIGINT         DEFAULT NULL COMMENT '挂号操作用户ID',
  create_time         DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time         DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_registration_reg_no (reg_no),
  KEY idx_registration_patient_id (patient_id),
  KEY idx_registration_schedule_id (schedule_id),
  KEY idx_registration_staff_id (staff_id),
  KEY idx_registration_status (status),
  KEY idx_registration_registrant_user_id (registrant_user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='挂号';

CREATE TABLE IF NOT EXISTS outpatient_visit (
  id                BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
  visit_no          VARCHAR(64)  NOT NULL COMMENT '就诊号',
  registration_id   BIGINT       NOT NULL COMMENT '挂号ID',
  patient_id        BIGINT       NOT NULL COMMENT '患者ID',
  staff_id          BIGINT       NOT NULL COMMENT '医生ID',
  visit_time        DATETIME     DEFAULT NULL COMMENT '就诊时间',
  chief_complaint   VARCHAR(500) DEFAULT NULL COMMENT '主诉',
  diagnosis         VARCHAR(500) DEFAULT NULL COMMENT '诊断',
  status            TINYINT      NOT NULL DEFAULT 0 COMMENT '就诊状态',
  create_time       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_outpatient_visit_no (visit_no),
  KEY idx_outpatient_visit_registration_id (registration_id),
  KEY idx_outpatient_visit_patient_id (patient_id),
  KEY idx_outpatient_visit_staff_id (staff_id),
  KEY idx_outpatient_visit_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='门诊就诊';

CREATE TABLE IF NOT EXISTS medical_item (
  id              BIGINT         NOT NULL AUTO_INCREMENT COMMENT '主键',
  item_code       VARCHAR(64)    NOT NULL COMMENT '项目编码',
  item_name       VARCHAR(128)   NOT NULL COMMENT '项目名称',
  item_type       TINYINT        NOT NULL COMMENT '项目类型',
  price           DECIMAL(12, 2) NOT NULL DEFAULT 0.00 COMMENT '单价',
  dept_id         BIGINT         DEFAULT NULL COMMENT '执行科室ID',
  status          TINYINT        NOT NULL DEFAULT 1 COMMENT '状态',
  create_time     DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time     DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_medical_item_code (item_code),
  KEY idx_medical_item_type (item_type),
  KEY idx_medical_item_dept_id (dept_id),
  KEY idx_medical_item_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='诊疗项目';

CREATE TABLE IF NOT EXISTS exam_request (
  id              BIGINT         NOT NULL AUTO_INCREMENT COMMENT '主键',
  request_no      VARCHAR(64)    NOT NULL COMMENT '申请单号',
  visit_id        BIGINT         NOT NULL COMMENT '就诊ID',
  patient_id      BIGINT         NOT NULL COMMENT '患者ID',
  item_id         BIGINT         NOT NULL COMMENT '项目ID',
  amount          DECIMAL(12, 2) NOT NULL DEFAULT 0.00 COMMENT '金额',
  status          TINYINT        NOT NULL DEFAULT 0 COMMENT '状态',
  create_time     DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time     DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_exam_request_no (request_no),
  KEY idx_exam_request_visit_id (visit_id),
  KEY idx_exam_request_patient_id (patient_id),
  KEY idx_exam_request_item_id (item_id),
  KEY idx_exam_request_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='检查检验申请';

-- ---------------------------------------------------------------------------
-- 4. 药品与处方
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS drug (
  id              BIGINT         NOT NULL AUTO_INCREMENT COMMENT '主键',
  drug_code       VARCHAR(64)    NOT NULL COMMENT '药品编码',
  drug_name       VARCHAR(128)   NOT NULL COMMENT '药品名称',
  spec            VARCHAR(128)   DEFAULT NULL COMMENT '规格',
  unit            VARCHAR(32)    DEFAULT NULL COMMENT '单位',
  price           DECIMAL(12, 2) NOT NULL DEFAULT 0.00 COMMENT '单价',
  manufacturer    VARCHAR(128)   DEFAULT NULL COMMENT '厂家',
  status          TINYINT        NOT NULL DEFAULT 1 COMMENT '状态',
  create_time     DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time     DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_drug_code (drug_code),
  KEY idx_drug_name (drug_name),
  KEY idx_drug_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='药品';

CREATE TABLE IF NOT EXISTS drug_stock (
  id              BIGINT         NOT NULL AUTO_INCREMENT COMMENT '主键',
  drug_id         BIGINT         NOT NULL COMMENT '药品ID',
  quantity        DECIMAL(12, 2) NOT NULL DEFAULT 0.00 COMMENT '库存数量',
  warn_quantity   DECIMAL(12, 2) NOT NULL DEFAULT 0.00 COMMENT '预警数量',
  update_time     DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_drug_stock_drug_id (drug_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='药品库存';

CREATE TABLE IF NOT EXISTS prescription (
  id              BIGINT         NOT NULL AUTO_INCREMENT COMMENT '主键',
  rx_no           VARCHAR(64)    NOT NULL COMMENT '处方号',
  visit_id        BIGINT         NOT NULL COMMENT '就诊ID',
  patient_id      BIGINT         NOT NULL COMMENT '患者ID',
  staff_id        BIGINT         NOT NULL COMMENT '开方医生ID',
  total_amount    DECIMAL(12, 2) NOT NULL DEFAULT 0.00 COMMENT '处方金额',
  status          TINYINT        NOT NULL DEFAULT 0 COMMENT '状态 2待发药等',
  create_time     DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time     DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_prescription_rx_no (rx_no),
  KEY idx_prescription_visit_id (visit_id),
  KEY idx_prescription_patient_id (patient_id),
  KEY idx_prescription_staff_id (staff_id),
  KEY idx_prescription_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='处方';

CREATE TABLE IF NOT EXISTS prescription_item (
  id                BIGINT         NOT NULL AUTO_INCREMENT COMMENT '主键',
  prescription_id   BIGINT         NOT NULL COMMENT '处方ID',
  drug_id           BIGINT         NOT NULL COMMENT '药品ID',
  quantity          DECIMAL(12, 2) NOT NULL DEFAULT 0.00 COMMENT '数量',
  unit_price        DECIMAL(12, 2) NOT NULL DEFAULT 0.00 COMMENT '单价',
  amount            DECIMAL(12, 2) NOT NULL DEFAULT 0.00 COMMENT '金额',
  usage_desc        VARCHAR(255)   DEFAULT NULL COMMENT '用法用量',
  PRIMARY KEY (id),
  KEY idx_prescription_item_rx_id (prescription_id),
  KEY idx_prescription_item_drug_id (drug_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='处方明细';

CREATE TABLE IF NOT EXISTS dispense_record (
  id                BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
  prescription_id   BIGINT       NOT NULL COMMENT '处方ID',
  pharmacist_id     BIGINT       DEFAULT NULL COMMENT '发药药师ID',
  dispense_time     DATETIME     DEFAULT NULL COMMENT '发药时间',
  status            TINYINT      NOT NULL DEFAULT 0 COMMENT '发药状态',
  PRIMARY KEY (id),
  KEY idx_dispense_record_prescription_id (prescription_id),
  KEY idx_dispense_record_pharmacist_id (pharmacist_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='发药记录';

-- ---------------------------------------------------------------------------
-- 5. 收费
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS charge_order (
  id              BIGINT         NOT NULL AUTO_INCREMENT COMMENT '主键',
  order_no        VARCHAR(64)    NOT NULL COMMENT '收费单号',
  patient_id      BIGINT         NOT NULL COMMENT '患者ID',
  visit_id        BIGINT         DEFAULT NULL COMMENT '就诊ID',
  total_amount    DECIMAL(12, 2) NOT NULL DEFAULT 0.00 COMMENT '应付金额',
  paid_amount     DECIMAL(12, 2) NOT NULL DEFAULT 0.00 COMMENT '实付金额',
  pay_type        TINYINT        DEFAULT NULL COMMENT '支付方式',
  pay_status      TINYINT        NOT NULL DEFAULT 0 COMMENT '支付状态 1已支付',
  cashier_id      BIGINT         DEFAULT NULL COMMENT '收银员ID',
  pay_time        DATETIME       DEFAULT NULL COMMENT '支付时间',
  create_time     DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time     DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_charge_order_no (order_no),
  KEY idx_charge_order_patient_id (patient_id),
  KEY idx_charge_order_visit_id (visit_id),
  KEY idx_charge_order_pay_status (pay_status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='收费单';

CREATE TABLE IF NOT EXISTS charge_detail (
  id                BIGINT         NOT NULL AUTO_INCREMENT COMMENT '主键',
  charge_order_id   BIGINT         NOT NULL COMMENT '收费单ID',
  biz_type          TINYINT        NOT NULL COMMENT '业务类型',
  biz_id            BIGINT         DEFAULT NULL COMMENT '业务单据ID',
  item_name         VARCHAR(128)   NOT NULL COMMENT '费用项名称',
  amount            DECIMAL(12, 2) NOT NULL DEFAULT 0.00 COMMENT '金额',
  PRIMARY KEY (id),
  KEY idx_charge_detail_order_id (charge_order_id),
  KEY idx_charge_detail_biz (biz_type, biz_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='收费明细';

-- ---------------------------------------------------------------------------
-- 6. AI 对话与知识库元数据
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS chat_messages (
  id                BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
  conversation_id   VARCHAR(64)  NOT NULL COMMENT '会话ID',
  user_id           BIGINT       NOT NULL COMMENT '发送者用户ID',
  role              VARCHAR(32)  NOT NULL COMMENT 'user/assistant',
  content           MEDIUMTEXT   NOT NULL COMMENT '消息纯文本',
  create_time       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (id),
  KEY idx_chat_messages_conversation_id (conversation_id),
  KEY idx_chat_messages_user_id (user_id),
  KEY idx_chat_messages_create_time (create_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='AI对话消息';

CREATE TABLE IF NOT EXISTS ai_knowledge_documents (
  id              BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
  document_id     VARCHAR(64)  NOT NULL COMMENT '文档业务ID',
  knowledge_base  VARCHAR(32)  NOT NULL COMMENT '知识库类型',
  original_name   VARCHAR(255) NOT NULL COMMENT '原始文件名',
  storage_path    VARCHAR(500) NOT NULL COMMENT '本地存储路径',
  content_type    VARCHAR(100) NOT NULL COMMENT 'MIME类型',
  file_size       BIGINT       NOT NULL COMMENT '文件大小',
  file_sha256     VARCHAR(64)  NOT NULL COMMENT '文件摘要',
  status          VARCHAR(32)  NOT NULL COMMENT 'PROCESSING/READY/FAILED/DELETING/DELETE_FAILED/DELETED',
  chunk_count     INT          NOT NULL DEFAULT 0 COMMENT '分块数量',
  error_message   VARCHAR(1000) DEFAULT NULL COMMENT '错误信息',
  uploaded_by     BIGINT       NOT NULL COMMENT '上传人用户ID',
  created_at      DATETIME     NOT NULL COMMENT '创建时间',
  updated_at      DATETIME     NOT NULL COMMENT '更新时间',
  completed_at    DATETIME     DEFAULT NULL COMMENT '完成时间',
  deleted_at      DATETIME     DEFAULT NULL COMMENT '删除时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_ai_knowledge_document_id (document_id),
  KEY idx_ai_knowledge_base_status (knowledge_base, status),
  KEY idx_ai_knowledge_sha256 (knowledge_base, file_sha256),
  KEY idx_ai_knowledge_uploaded_by (uploaded_by)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='知识库文档元数据';
