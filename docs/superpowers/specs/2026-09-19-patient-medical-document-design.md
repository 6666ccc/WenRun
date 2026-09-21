# 患者就医资料 — 设计文档

日期：2026-09-19  
范围：`docs/SQL/`、`backend-java/`、`frontend/`。不接腾讯云 COS SDK，不改 AI 服务。

## 1. 背景与目标

个人档案「就医资料」Tab 和健康数据里的四宫格（病历 / 报告单 / 药物 / 体检报告）目前是套壳。患者会把图片或 PDF 传到 COS，拿到地址后再登记到本院档案。

目标：落一张元数据表，按「份」列出、计数、删除；文件二进制仍在对象存储。授权与健康指标同一套：`patient_id` 是主体，登录账号只做操作者。

## 2. 已确认取舍

| 项 | 选择 |
| --- | --- |
| 粒度 | 一份资料 = 一次上传批次，可挂多个文件 |
| 文件 | 图片 + PDF |
| 归属 | `patient_id`；上传人 `uploaded_by_user_id` |
| 分类 | 固定四类，无 OTHER |
| 挂号 | 不关联 `registration_id` |
| 存储形态 | 一张表；多文件放 `files_json` |
| 对象存储 | 调用方先传到 COS，后端只收稳定 URL |
| 删除 | 整份逻辑删除；不单独删某一页 |
| 第一期不做 | COS SDK / 预签名、OCR、医生端、按页删除、孤儿对象对账 |

## 3. 表

`patient_medical_document`，约定与现库一致：InnoDB / utf8mb4，主键自增，不加外键。

```sql
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
```

`files_json` 元素：

```json
{
  "url": "https://bucket.cos.ap-guangzhou.myqcloud.com/patient/3/a.jpg",
  "contentType": "image/jpeg",
  "originalName": "report-p1.jpg",
  "size": 245800
}
```

`size` 可空。数组顺序即页序。

列表排序：`ORDER BY COALESCE(occurred_at, created_at) DESC, id DESC`。

## 4. URL 规则

入库前去掉 URL 的 query 和 fragment（COS 签名参数不能当档案地址）。

只接受 `http` / `https`。拒绝空、相对路径、`javascript:` 等。去参后长度 1–500。

第一期接口原样返回入库后的稳定 URL，不签发临时 GET。私有桶浏览器预览留到 COS 接入后再做。

## 5. 校验

`doc_type` 仅：

| code | 中文 |
| --- | --- |
| `MEDICAL_RECORD` | 病历 |
| `LAB_REPORT` | 报告单 |
| `MEDICATION` | 药物 |
| `CHECKUP` | 体检报告 |

其它约束：

- `files` 1–9 项。
- `contentType` 仅：`image/jpeg`、`image/png`、`image/webp`、`image/heic`、`image/heif`、`application/pdf`。`image/jpg` 视为 `image/jpeg`。
- `originalName` 可空，最长 255。
- `title` 可空，最长 128；空白当 null。
- `occurred_at` 可空，不可晚于当前时间 1 天以上（允许轻微时钟偏差）。
- 无权患者：与指标接口相同，走 `PatientAccessService.requireAccessible`，文案「无权访问该患者」。

第一期不提供改文件列表的更新接口。要改就删掉重传。标题/分类/日期也不做 PATCH。

## 6. API

路径挂在当前活动患者下，不信任请求体里的 `userId` / `patientId`。

| 方法 | 路径 | 作用 |
| --- | --- | --- |
| GET | `/api/patients/{patientId}/medical-documents/counts` | 四类未删除份数 |
| GET | `/api/patients/{patientId}/medical-documents?docType=&limit=` | 列表，`docType` 可空 |
| GET | `/api/patients/{patientId}/medical-documents/{id}` | 详情 |
| POST | `/api/patients/{patientId}/medical-documents` | 登记一份 |
| DELETE | `/api/patients/{patientId}/medical-documents/{id}` | 逻辑删除 |

POST 体：

```json
{
  "docType": "LAB_REPORT",
  "title": "2026-09 血常规",
  "occurredAt": "2026-09-18T09:00:00",
  "files": [
    {
      "url": "https://bucket.cos.ap-guangzhou.myqcloud.com/p/3/a.jpg?q-sign-algorithm=sha1&q-ak=tmp",
      "contentType": "image/jpeg",
      "originalName": "a.jpg",
      "size": 1200
    }
  ]
}
```

服务端会把上述 URL 存成无 query 的地址。`uploaded_by_user_id` 只来自 `UserContext`。

VO 增加 `docTypeName`、`fileCount`，以及规范化后的 `files`。

默认 `limit=50`，最大 `200`。

## 7. 前端

- 去掉就医资料套壳和「数据库还未设计」。
- 快捷操作「上传就医资料」打开 `/archive?tab=documents` 并进入登记表单。
- 健康数据四宫格显示「共 N 份」，点击进就医资料 Tab（可带 `docType` 以便滚动到该类）。
- 就医资料 Tab：四类分组列表、预览链接、整份删除、登记表单（类型、标题、发生时间、多个文件 URL + MIME + 文件名）。
- 请求一律用 `activePatientId`。
- 运动睡眠、腰围、WHtR、「上传健康数据」仍套壳。

第一期不在浏览器直传 COS。表单提交的是调用方已经拿到的稳定/可去签 URL。

## 8. 错误

- 未登录：现有 401。
- 无权：业务错误「无权访问该患者」。
- 校验失败：具体中文（类型不支持、至少上传 1 个文件、URL 非法等）。
- 删除不存在或已删： 「就医资料不存在」。

## 9. 测试

- Java：枚举、URL 去签、files 校验、无权拒绝、创建后列表/计数、软删后不可见。
- 前端：`node --test` 覆盖类型文案、去 query、四宫格不再写「数据库还未设计」。
- 命令：`backend-java` 下 `mvn -q test`；`frontend` 下 `npm test`。

## 10. 不在范围内

- 腾讯云 / 阿里云 SDK、预签名 PUT/GET、回调对账。
- 把文件存进 MySQL。
- 关联挂号、AI 读病历、OCR 写入指标。
- 医生 portal 独立 UI（临床账号若调同一 API，仍走现有 `PatientAccessService` 旁路）。
