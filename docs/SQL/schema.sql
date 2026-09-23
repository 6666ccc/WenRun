-- WenRun 轻量运行库建表脚本
-- 当前运行边界：账号、患者档案、健康档案、健康指标纵向记录、就医资料、专家/号源、在线挂号与 AI Agent 元数据。
-- 科室和医护表仅作为挂号及 Agent 查询的兼容基础数据，不再对应独立前端模块。
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
-- 3. 患者与在线挂号
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS patient (
  id              BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
  patient_no      VARCHAR(64)  NOT NULL COMMENT '患者编号',
  name            VARCHAR(64)  NOT NULL COMMENT '姓名',
  gender          TINYINT      DEFAULT NULL COMMENT '0女 1男 2未知',
  birth_date      DATE         DEFAULT NULL COMMENT '出生日期',
  id_card         VARCHAR(32)  DEFAULT NULL COMMENT '身份证号',
  phone           VARCHAR(20)  DEFAULT NULL COMMENT '手机号',
  user_id         BIGINT       DEFAULT NULL COMMENT '主账号/创建账号，对应 sys_user.id；不作授权依据',
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

CREATE TABLE IF NOT EXISTS user_patient_relation (
  id                     BIGINT      NOT NULL AUTO_INCREMENT COMMENT '主键',
  user_id                BIGINT      NOT NULL COMMENT '登录账号ID，对应 sys_user.id',
  patient_id             BIGINT      NOT NULL COMMENT '患者ID，对应 patient.id',
  relation_type          VARCHAR(32) NOT NULL COMMENT 'SELF/SPOUSE/CHILD/PARENT/OTHER',
  is_default             TINYINT     NOT NULL DEFAULT 0 COMMENT '是否为该账号当前默认患者',
  status                 TINYINT     NOT NULL DEFAULT 1 COMMENT '1有效 0停用',
  active_default_user_id BIGINT GENERATED ALWAYS AS (
    CASE WHEN status = 1 AND is_default = 1 THEN user_id ELSE NULL END
  ) STORED COMMENT '用于保证每个账号至多一个有效默认患者',
  active_self_user_id    BIGINT GENERATED ALWAYS AS (
    CASE WHEN status = 1 AND relation_type = 'SELF' THEN user_id ELSE NULL END
  ) STORED COMMENT '用于保证每个账号至多一个有效本人患者',
  created_at             DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  updated_at             DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_user_patient (user_id, patient_id),
  UNIQUE KEY uk_user_patient_active_default (active_default_user_id),
  UNIQUE KEY uk_user_patient_active_self (active_self_user_id),
  KEY idx_user_patient_active_list (user_id, status, is_default, id),
  KEY idx_patient_user_active (patient_id, status, user_id),
  CONSTRAINT chk_user_patient_relation_type
    CHECK (relation_type IN ('SELF', 'SPOUSE', 'CHILD', 'PARENT', 'OTHER')),
  CONSTRAINT chk_user_patient_is_default CHECK (is_default IN (0, 1)),
  CONSTRAINT chk_user_patient_status CHECK (status IN (0, 1)),
  CONSTRAINT chk_user_patient_inactive_not_default CHECK (status = 1 OR is_default = 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='账号与患者授权关系；授权只认此表';

CREATE TABLE IF NOT EXISTS patient_health_profile (
  id                  BIGINT         NOT NULL AUTO_INCREMENT COMMENT '主键',
  patient_id          BIGINT         NOT NULL COMMENT '患者ID，对应 patient.id',
  height_cm           DECIMAL(5, 1)  DEFAULT NULL COMMENT '身高cm',
  weight_kg           DECIMAL(5, 1)  DEFAULT NULL COMMENT '体重kg',
  waist_cm            DECIMAL(5, 1)  DEFAULT NULL COMMENT '腰围cm',
  whtr                DECIMAL(5, 3)  GENERATED ALWAYS AS (
                        CASE
                          WHEN height_cm > 0 AND waist_cm IS NOT NULL
                          THEN ROUND(waist_cm / height_cm, 3)
                          ELSE NULL
                        END
                      ) STORED COMMENT '腰围身高比，由腰围/身高自动计算',
  systolic_mmhg       SMALLINT       DEFAULT NULL COMMENT '收缩压mmHg',
  diastolic_mmhg      SMALLINT       DEFAULT NULL COMMENT '舒张压mmHg',
  glucose_mmol        DECIMAL(4, 1)  DEFAULT NULL COMMENT '血糖mmol/L',
  glucose_type        VARCHAR(24)    DEFAULT NULL COMMENT 'fasting空腹 / random随机 / postprandial餐后',
  heart_rate_bpm      SMALLINT       DEFAULT NULL COMMENT '心率次/分',
  spo2_pct            SMALLINT       DEFAULT NULL COMMENT '血氧%',
  respiratory_rate_bpm SMALLINT      DEFAULT NULL COMMENT '呼吸频率次/分',
  temperature_c       DECIMAL(4, 1)  DEFAULT NULL COMMENT '体温℃',
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
  waist_cm            DECIMAL(5, 1)  DEFAULT NULL COMMENT '腰围cm',
  whtr                DECIMAL(5, 3)  GENERATED ALWAYS AS (
                        CASE
                          WHEN height_cm > 0 AND waist_cm IS NOT NULL
                          THEN ROUND(waist_cm / height_cm, 3)
                          ELSE NULL
                        END
                      ) STORED COMMENT '腰围身高比，由腰围/身高自动计算',
  systolic_mmhg       SMALLINT       DEFAULT NULL COMMENT '收缩压mmHg',
  diastolic_mmhg      SMALLINT       DEFAULT NULL COMMENT '舒张压mmHg',
  glucose_mmol        DECIMAL(4, 1)  DEFAULT NULL COMMENT '血糖mmol/L',
  glucose_type        VARCHAR(24)    DEFAULT NULL COMMENT 'fasting空腹 / random随机 / postprandial餐后',
  heart_rate_bpm      SMALLINT       DEFAULT NULL COMMENT '心率次/分',
  spo2_pct            SMALLINT       DEFAULT NULL COMMENT '血氧%',
  respiratory_rate_bpm SMALLINT      DEFAULT NULL COMMENT '呼吸频率次/分',
  temperature_c       DECIMAL(4, 1)  DEFAULT NULL COMMENT '体温℃',
  measured_at         DATETIME       NOT NULL COMMENT '用户确认的测量/填写时间',
  past_history        VARCHAR(2000)  DEFAULT NULL COMMENT '既往史',
  family_history      VARCHAR(2000)  DEFAULT NULL COMMENT '家族史',
  personal_history    VARCHAR(2000)  DEFAULT NULL COMMENT '个人史',
  create_time         DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '系统写入时间',
  PRIMARY KEY (id),
  KEY idx_health_snapshot_patient_time (patient_id, measured_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='患者健康档案历史快照';

-- 健康指标纵向记录：一行 = 某患者在某时刻的一项指标。
-- 身高、腰围当前值在 patient_health_profile；BMI 不落库，WHtR 由生成列自动计算。
-- 趋势图必须按 measured_at 排序，不能按 created_at（支持补录历史数据）。
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

-- 就医资料：一份资料一行，COS/OSS 稳定 URL 存在 files_json。
-- 归属 patient_id；uploaded_by_user_id 是上传人，不是资料主人。不关联 registration。
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
  idempotency_key     VARCHAR(128)   DEFAULT NULL COMMENT 'AI挂号幂等键',
  create_time         DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time         DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_registration_reg_no (reg_no),
  UNIQUE KEY uk_registration_idempotency_key (idempotency_key),
  KEY idx_registration_patient_id (patient_id),
  KEY idx_registration_schedule_id (schedule_id),
  KEY idx_registration_staff_id (staff_id),
  KEY idx_registration_status (status),
  KEY idx_registration_registrant_user_id (registrant_user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='挂号';

-- ---------------------------------------------------------------------------
-- 4. AI 对话与知识库元数据
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS ai_conversations (
  user_id          BIGINT       NOT NULL COMMENT '会话发起者账号ID，对应 sys_user.id',
  conversation_id  VARCHAR(64)  NOT NULL COMMENT '用户作用域内的会话ID',
  patient_id       BIGINT       NOT NULL COMMENT '当前会话讨论的患者ID，对应 patient.id；会话内不可切换',
  status           VARCHAR(24)  NOT NULL DEFAULT 'active' COMMENT 'active',
  version          BIGINT       NOT NULL DEFAULT 0 COMMENT '会话状态乐观版本',
  create_time      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  deleted_time     DATETIME     NULL COMMENT '软删除时间',
  PRIMARY KEY (user_id, conversation_id),
  KEY idx_ai_conversations_update_time (update_time),
  KEY idx_ai_conversations_user_patient_update (user_id, patient_id, update_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='AI会话归属';

CREATE TABLE IF NOT EXISTS chat_messages (
  id                BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
  conversation_id   VARCHAR(64)  NOT NULL COMMENT '会话ID，仅在 user_id 作用域内唯一',
  user_id           BIGINT       NOT NULL COMMENT '会话所有者账号ID；患者主体以 ai_conversations.patient_id 为准',
  client_request_id VARCHAR(64)  NULL COMMENT '客户端对话轮次幂等键',
  role              VARCHAR(32)  NOT NULL COMMENT 'user/assistant',
  content           MEDIUMTEXT   NOT NULL COMMENT '消息纯文本',
  metadata_json     JSON         NULL COMMENT 'SSE确认状态等可恢复UI元数据',
  create_time       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (id),
  KEY idx_chat_messages_conversation_id (conversation_id),
  KEY idx_chat_messages_user_id (user_id),
  KEY idx_chat_messages_create_time (create_time),
  KEY idx_chat_messages_user_conversation_time (user_id, conversation_id, create_time, id),
  UNIQUE KEY uk_chat_messages_client_request (user_id, conversation_id, client_request_id, role)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='AI对话消息';

CREATE TABLE IF NOT EXISTS ai_patient_memories (
  id                     BIGINT       NOT NULL AUTO_INCREMENT COMMENT '修订记录主键',
  memory_id              VARCHAR(64)  NOT NULL COMMENT '跨修订稳定的记忆ID',
  patient_id             BIGINT       NOT NULL COMMENT '患者ID',
  type                   VARCHAR(40)  NOT NULL COMMENT '受控记忆类型',
  content                VARCHAR(500) NOT NULL COMMENT '患者明确声明的偏好',
  source_conversation_id VARCHAR(64)  NOT NULL COMMENT '来源会话',
  source_message_id      BIGINT       NOT NULL COMMENT '来源用户消息',
  status                 VARCHAR(24)  NOT NULL DEFAULT 'active' COMMENT 'pending/active/superseded/deleted',
  version                INT          NOT NULL DEFAULT 1 COMMENT '修订版本',
  confidence             DECIMAL(5,4) NOT NULL DEFAULT 1.0000 COMMENT '显式声明默认1',
  expire_time            DATETIME     NULL COMMENT '过期时间',
  create_time            DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  update_time            DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  deleted_time           DATETIME     NULL COMMENT '删除时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_ai_patient_memory_revision (memory_id, version),
  KEY idx_ai_patient_memory_active (patient_id, status, expire_time, update_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='受治理的AI患者偏好记忆及版本';

CREATE TABLE IF NOT EXISTS ai_knowledge_documents (
  id              BIGINT       NOT NULL AUTO_INCREMENT COMMENT '主键',
  document_id     VARCHAR(64)  NOT NULL COMMENT '文档业务ID',
  version         INT          NOT NULL DEFAULT 1 COMMENT '文档修订版本',
  knowledge_base  VARCHAR(32)  NOT NULL COMMENT '知识库类型',
  original_name   VARCHAR(255) NOT NULL COMMENT '原始文件名',
  storage_path    VARCHAR(500) NOT NULL COMMENT '本地存储路径',
  content_type    VARCHAR(100) NOT NULL COMMENT 'MIME类型',
  file_size       BIGINT       NOT NULL COMMENT '文件大小',
  file_sha256     VARCHAR(64)  NOT NULL COMMENT '文件摘要',
  status          VARCHAR(32)  NOT NULL COMMENT 'processing/active/superseded/inactive/deleting/deleted/failed',
  effective_from  DATETIME     DEFAULT NULL COMMENT '开始参与在线检索的时间',
  expires_at      DATETIME     DEFAULT NULL COMMENT '停止参与在线检索的时间',
  chunk_count     INT          NOT NULL DEFAULT 0 COMMENT '分块数量',
  qdrant_sync_status VARCHAR(24) NOT NULL DEFAULT 'synced' COMMENT 'synced/reconcile_required',
  operation_id    VARCHAR(64)  DEFAULT NULL COMMENT '补偿和重试操作ID',
  error_message   VARCHAR(1000) DEFAULT NULL COMMENT '错误信息',
  uploaded_by     BIGINT       NOT NULL COMMENT '上传人用户ID',
  created_at      DATETIME     NOT NULL COMMENT '创建时间',
  updated_at      DATETIME     NOT NULL COMMENT '更新时间',
  completed_at    DATETIME     DEFAULT NULL COMMENT '完成时间',
  deleted_at      DATETIME     DEFAULT NULL COMMENT '删除时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_ai_knowledge_document_revision (document_id, version),
  KEY idx_ai_knowledge_base_status (knowledge_base, status),
  KEY idx_ai_knowledge_effective (knowledge_base, status, effective_from, expires_at),
  KEY idx_ai_knowledge_sha256 (knowledge_base, file_sha256),
  KEY idx_ai_knowledge_uploaded_by (uploaded_by),
  KEY idx_ai_knowledge_operation (operation_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='知识库文档元数据';
