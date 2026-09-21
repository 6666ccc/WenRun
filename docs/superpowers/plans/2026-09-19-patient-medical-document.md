# 患者就医资料 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为患者档案增加就医资料：一张 `patient_medical_document` 表、按患者授权的登记/列表/删除接口，以及档案页四宫格与资料 Tab。

**Architecture:** 一份资料一行。调用方先把图片/PDF 传到 COS，再把去签名后的稳定 URL 写入 `files_json`。医疗主体是 `patient_id`，上传人是 `uploaded_by_user_id`。权限只走 `PatientAccessService.requireAccessible`。

**Tech Stack:** MySQL 8 JSON、MyBatis XML、Spring MVC、Vue 3 `<script setup>`、JUnit 5、`node --test`。

**Spec:** `docs/superpowers/specs/2026-09-19-patient-medical-document-design.md`

## Global Constraints

- 不接 COS / OSS SDK，不签发预签名，不把文件二进制写入 MySQL。
- 不关联 `registration_id`，不做 OTHER 分类，不单独删某一页，不做 PATCH。
- 医疗查询与写入一律 `patient_id`；`uploaded_by_user_id` 只来自 `UserContext.getUserId()`。
- 入库 URL 必须去掉 query 和 fragment。
- `doc_type` 仅 `MEDICAL_RECORD` / `LAB_REPORT` / `MEDICATION` / `CHECKUP`。
- 命令：`backend-java` 下 `mvn -q test`；`frontend` 下 `npm test`。
- 不提交 git，除非用户明确要求。每个任务完成后不要 `git commit`。

---

## File Structure

| 文件 | 操作 | 职责 |
| --- | --- | --- |
| `docs/SQL/schema.sql` | 修改 | 全量建表增加 `patient_medical_document` |
| `docs/SQL/migrations/2026-09-19-patient-medical-document.sql` | 创建 | 已有库的幂等迁移 |
| `backend-java/src/main/java/com/wenrun/enums/MedicalDocumentType.java` | 创建 | 四类英文枚举 |
| `backend-java/src/main/java/com/wenrun/util/MedicalDocumentFiles.java` | 创建 | URL 去签、files 校验与 JSON |
| `backend-java/src/main/java/com/wenrun/dto/MedicalDocumentFileItem.java` | 创建 | 单个文件 |
| `backend-java/src/main/java/com/wenrun/dto/MedicalDocumentDTO.java` | 创建 | 登记请求 |
| `backend-java/src/main/java/com/wenrun/vo/MedicalDocumentVO.java` | 创建 | 详情/列表 |
| `backend-java/src/main/java/com/wenrun/vo/MedicalDocumentCountVO.java` | 创建 | 分类计数 |
| `backend-java/src/main/java/com/wenrun/entity/PatientMedicalDocument.java` | 创建 | 表映射，`filesJson` 为 String |
| `backend-java/src/main/java/com/wenrun/repository/PatientMedicalDocumentRepository.java` | 创建 | Mapper 接口 |
| `backend-java/src/main/resources/mapper/PatientMedicalDocumentRepository.xml` | 创建 | SQL |
| `backend-java/src/main/java/com/wenrun/service/PatientMedicalDocumentService.java` | 创建 | 服务接口 |
| `backend-java/src/main/java/com/wenrun/service/impl/PatientMedicalDocumentServiceImpl.java` | 创建 | 授权、校验、软删 |
| `backend-java/src/main/java/com/wenrun/controller/PatientMedicalDocumentController.java` | 创建 | REST |
| `backend-java/src/test/java/com/wenrun/enums/MedicalDocumentTypeTest.java` | 创建 | 枚举 |
| `backend-java/src/test/java/com/wenrun/util/MedicalDocumentFilesTest.java` | 创建 | URL / files |
| `backend-java/src/test/java/com/wenrun/service/impl/PatientMedicalDocumentServiceImplTest.java` | 创建 | 服务 |
| `backend-java/src/test/java/com/wenrun/repository/PatientMedicalDocumentRepositoryXmlTest.java` | 创建 | Mapper 文本约束 |
| `frontend/src/features/archive/documents.js` | 创建 | 类型文案与 URL 去签 |
| `frontend/src/api/modules/medicalDocument.js` | 创建 | API |
| `frontend/src/api/modules/index.js` | 修改 | 导出 |
| `frontend/src/components/archive/ArchiveDocuments.vue` | 创建 | 资料 Tab |
| `frontend/src/components/archive/ArchiveHealthData.vue` | 修改 | 四宫格接计数 |
| `frontend/src/components/archive/ArchiveSidebar.vue` | 修改 | 上传入口打开资料 Tab |
| `frontend/src/views/PatientArchive.vue` | 修改 | 拉数、换套壳为真实 Tab |
| `frontend/src/features/archive/tabs.js` | 修改 | 可选 `docType` query |
| `frontend/test/medical-document.test.js` | 创建 | 前端纯函数 |
| `frontend/test/archive.test.js` | 修改 | 不再把就医资料当未设计 |

---

### Task 1: 建表脚本

**Files:**
- Modify: `docs/SQL/schema.sql`
- Create: `docs/SQL/migrations/2026-09-19-patient-medical-document.sql`

**Interfaces:**
- Produces: 表 `patient_medical_document`，列与 spec 第 3 节完全一致

- [ ] **Step 1: 在 schema.sql 头部运行边界补上就医资料**

把文件头「当前运行边界」那句改成包含就医资料。在 `health_metric_record` 与 `registration` 之间插入完整 `CREATE TABLE`（见 spec 第 3 节，逐字复制）。

- [ ] **Step 2: 写迁移脚本**

`docs/SQL/migrations/2026-09-19-patient-medical-document.sql`：

```sql
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
```

本地已有 `wenrun` 库时执行该迁移（环境若已执行可跳过）。**不要**对生产做未确认的破坏性操作。

- [ ] **Step 3: 确认两份 DDL 列名一致**

`schema.sql` 与迁移文件都必须含：`patient_id`、`doc_type`、`files_json`、`uploaded_by_user_id`、`is_deleted`；都**不得**含 `user_id`、`registration_id`、`owner_id`。

---

### Task 2: 文档类型枚举

**Files:**
- Create: `backend-java/src/main/java/com/wenrun/enums/MedicalDocumentType.java`
- Test: `backend-java/src/test/java/com/wenrun/enums/MedicalDocumentTypeTest.java`

**Interfaces:**
- Produces:
  - `MedicalDocumentType`：`MEDICAL_RECORD` / `LAB_REPORT` / `MEDICATION` / `CHECKUP`
  - `getCode()` → `name()`
  - `getDisplayName()` → 病历 / 报告单 / 药物 / 体检报告
  - `fromCode(String): Optional<MedicalDocumentType>`，忽略大小写；未知返回 empty

- [ ] **Step 1: Write the failing test**

```java
package com.wenrun.enums;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class MedicalDocumentTypeTest {

    @Test
    void storesEnglishCodeWithFixedChineseName() {
        assertEquals("MEDICAL_RECORD", MedicalDocumentType.MEDICAL_RECORD.getCode());
        assertEquals("病历", MedicalDocumentType.MEDICAL_RECORD.getDisplayName());
        assertEquals("报告单", MedicalDocumentType.LAB_REPORT.getDisplayName());
        assertEquals("药物", MedicalDocumentType.MEDICATION.getDisplayName());
        assertEquals("体检报告", MedicalDocumentType.CHECKUP.getDisplayName());
        assertEquals(4, MedicalDocumentType.values().length);
    }

    @Test
    void fromCodeAcceptsEnglishEnumValueIgnoreCase() {
        assertEquals(MedicalDocumentType.LAB_REPORT, MedicalDocumentType.fromCode("lab_report").orElseThrow());
        assertTrue(MedicalDocumentType.fromCode("OTHER").isEmpty());
        assertTrue(MedicalDocumentType.fromCode(null).isEmpty());
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `mvn -q -Dtest=MedicalDocumentTypeTest test`（在 `backend-java/`）

Expected: FAIL，类不存在。

- [ ] **Step 3: Write minimal implementation**

照 `HealthMetricType` 的 `fromCode` 写法实现 `MedicalDocumentType`，四个常量带中文 `displayName`。不要加 `OTHER`。

- [ ] **Step 4: Run test to verify it passes**

Run: `mvn -q -Dtest=MedicalDocumentTypeTest test`

Expected: PASS。

---

### Task 3: URL 去签与 files 校验

**Files:**
- Create: `backend-java/src/main/java/com/wenrun/dto/MedicalDocumentFileItem.java`
- Create: `backend-java/src/main/java/com/wenrun/util/MedicalDocumentFiles.java`
- Test: `backend-java/src/test/java/com/wenrun/util/MedicalDocumentFilesTest.java`

**Interfaces:**
- Produces:
  - `MedicalDocumentFileItem`：`url`、`contentType`、`originalName`、`size`（`Long`，可空）
  - `MedicalDocumentFiles.canonicalUrl(String raw): String`；非法抛 `BusinessException("文件地址不合法")`
  - `MedicalDocumentFiles.normalize(List<MedicalDocumentFileItem>): List<MedicalDocumentFileItem>`
  - `MedicalDocumentFiles.toJson(List<MedicalDocumentFileItem>): String`
  - `MedicalDocumentFiles.fromJson(String): List<MedicalDocumentFileItem>`
  - 常量：`MIN_FILES=1`、`MAX_FILES=9`、`MAX_URL_LENGTH=500`、`MAX_NAME_LENGTH=255`、`MAX_TITLE_LENGTH=128`
  - `normalize` 失败文案：
    - 空/超出 9：`至少上传 1 个文件，至多 9 个`
    - MIME 不支持：`不支持的文件类型`
    - 文件名为空以外但超长：`文件名过长`

- [ ] **Step 1: Write the failing test**

```java
package com.wenrun.util;

import com.wenrun.common.exception.BusinessException;
import com.wenrun.dto.MedicalDocumentFileItem;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

class MedicalDocumentFilesTest {

    @Test
    void canonicalUrlStripsQueryAndFragment() {
        String raw = "https://bucket.cos.ap-guangzhou.myqcloud.com/patient/3/a.jpg?q-sign-algorithm=sha1&q-ak=tmp#x";
        assertEquals(
                "https://bucket.cos.ap-guangzhou.myqcloud.com/patient/3/a.jpg",
                MedicalDocumentFiles.canonicalUrl(raw));
    }

    @Test
    void canonicalUrlRejectsNonHttp() {
        BusinessException ex = assertThrows(BusinessException.class,
                () -> MedicalDocumentFiles.canonicalUrl("javascript:alert(1)"));
        assertEquals("文件地址不合法", ex.getMessage());
    }

    @Test
    void normalizeAcceptsJpegAliasAndKeepsOrder() {
        MedicalDocumentFileItem first = item("https://x.com/a.jpg?token=1", "image/jpg", "a.jpg", 10L);
        MedicalDocumentFileItem second = item("https://x.com/b.pdf", "application/pdf", "b.pdf", null);
        List<MedicalDocumentFileItem> out = MedicalDocumentFiles.normalize(List.of(first, second));
        assertEquals("https://x.com/a.jpg", out.get(0).getUrl());
        assertEquals("image/jpeg", out.get(0).getContentType());
        assertEquals("application/pdf", out.get(1).getContentType());
        assertEquals("b.pdf", out.get(1).getOriginalName());
    }

    @Test
    void normalizeRejectsEmptyAndUnknownMime() {
        BusinessException empty = assertThrows(BusinessException.class,
                () -> MedicalDocumentFiles.normalize(List.of()));
        assertTrue(empty.getMessage().contains("至少上传 1 个文件"));
        MedicalDocumentFileItem bad = item("https://x.com/a.exe", "application/octet-stream", "a.exe", 1L);
        BusinessException mime = assertThrows(BusinessException.class,
                () -> MedicalDocumentFiles.normalize(List.of(bad)));
        assertEquals("不支持的文件类型", mime.getMessage());
    }

    @Test
    void jsonRoundTrip() {
        List<MedicalDocumentFileItem> files = MedicalDocumentFiles.normalize(List.of(
                item("https://x.com/a.png", "image/png", "a.png", 8L)));
        String json = MedicalDocumentFiles.toJson(files);
        assertEquals("https://x.com/a.png", MedicalDocumentFiles.fromJson(json).get(0).getUrl());
    }

    private static MedicalDocumentFileItem item(String url, String type, String name, Long size) {
        MedicalDocumentFileItem item = new MedicalDocumentFileItem();
        item.setUrl(url);
        item.setContentType(type);
        item.setOriginalName(name);
        item.setSize(size);
        return item;
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `mvn -q -Dtest=MedicalDocumentFilesTest test`

Expected: FAIL，类不存在。

- [ ] **Step 3: Write minimal implementation**

`MedicalDocumentFileItem` 用 Lombok `@Data`。

`MedicalDocumentFiles` 要点：

- `canonicalUrl`：trim；`URI` 解析；scheme 仅 http/https；用 `new URI(scheme, authority, path, null, null)` 重建（path 空则 `/`）；长度 1–500，否则 `文件地址不合法`。
- `image/jpg` → `image/jpeg`。允许的 MIME：`image/jpeg`、`image/png`、`image/webp`、`image/heic`、`image/heif`、`application/pdf`（比较时忽略大小写）。
- `originalName` blank → null；非空则 trim，超 255 抛 `文件名过长`。
- `size` 若非 null 且 `< 0` 抛 `文件大小不合法`。
- JSON 用 `com.fasterxml.jackson.databind.ObjectMapper` 的静态实例；失败转 `BusinessException("文件列表无法解析")`。

- [ ] **Step 4: Run test to verify it passes**

Run: `mvn -q -Dtest=MedicalDocumentFilesTest test`

Expected: PASS。

---

### Task 4: 持久化

**Files:**
- Create: `backend-java/src/main/java/com/wenrun/entity/PatientMedicalDocument.java`
- Create: `backend-java/src/main/java/com/wenrun/repository/PatientMedicalDocumentRepository.java`
- Create: `backend-java/src/main/resources/mapper/PatientMedicalDocumentRepository.xml`
- Test: `backend-java/src/test/java/com/wenrun/repository/PatientMedicalDocumentRepositoryXmlTest.java`

**Interfaces:**
- Entity 字段：`id`、`patientId`、`docType`、`title`、`occurredAt`、`filesJson`（String）、`uploadedByUserId`、`createdAt`、`updatedAt`、`isDeleted`（Integer）
- Mapper：
  - `selectByIdAndPatientId(id, patientId)`
  - `selectRecent(patientId, docType, limit)` — `docType` 可空
  - `selectCounts(patientId)` 返回 `List<MedicalDocumentCountVO>`（可只填 `docType`+`count`，name 由服务补）
  - `insert(entity)` `useGeneratedKeys`
  - `softDeleteByIdAndPatientId(id, patientId)`
- 列表 SQL：`WHERE patient_id=? AND is_deleted=0`，可选 `AND doc_type=?`，`ORDER BY COALESCE(occurred_at, created_at) DESC, id DESC LIMIT #{limit}`
- 计数 SQL：`SELECT doc_type AS docType, COUNT(*) AS count FROM ... WHERE patient_id=? AND is_deleted=0 GROUP BY doc_type`

- [ ] **Step 1: Write the failing XML test**

照 `HealthMetricRecordRepositoryXmlTest` 解析 mapper XML：

- `selectRecent` 含 `patient_id`、`is_deleted = 0`、`COALESCE(occurred_at, created_at)`，不含 `user_id`
- `softDelete` 设 `is_deleted = 1` 且带 `patient_id`
- `insert` 含 `uploaded_by_user_id`、`files_json`，不含 `registration_id`

- [ ] **Step 2: Run test to verify it fails**

Run: `mvn -q -Dtest=PatientMedicalDocumentRepositoryXmlTest test`

Expected: FAIL，XML 不存在。

- [ ] **Step 3: Write entity / repository / XML**

`MedicalDocumentCountVO` 可在本任务一并创建（`docType`、`docTypeName`、`count`），mapper 只映射前两个计数字段。

- [ ] **Step 4: Run test to verify it passes**

Run: `mvn -q -Dtest=PatientMedicalDocumentRepositoryXmlTest test`

Expected: PASS。

---

### Task 5: 服务层

**Files:**
- Create: `backend-java/src/main/java/com/wenrun/dto/MedicalDocumentDTO.java`
- Create: `backend-java/src/main/java/com/wenrun/vo/MedicalDocumentVO.java`
- Create: `backend-java/src/main/java/com/wenrun/vo/MedicalDocumentCountVO.java`（若 Task 4 已建则跳过）
- Create: `backend-java/src/main/java/com/wenrun/service/PatientMedicalDocumentService.java`
- Create: `backend-java/src/main/java/com/wenrun/service/impl/PatientMedicalDocumentServiceImpl.java`
- Test: `backend-java/src/test/java/com/wenrun/service/impl/PatientMedicalDocumentServiceImplTest.java`

**Interfaces:**
- DTO：`docType`、`title`、`occurredAt`、`files`（`List<MedicalDocumentFileItem>`）
- VO：`id`、`docType`、`docTypeName`、`title`、`occurredAt`、`files`、`fileCount`、`createdAt`、`updatedAt`（不要把 `uploadedByUserId` 暴露给患者端，除非调试需要；第一期不暴露）
- Service：
  - `List<MedicalDocumentCountVO> counts(Long patientId)` — 四类都返回，缺的 count=0
  - `List<MedicalDocumentVO> list(Long patientId, String docType, Integer limit)`
  - `MedicalDocumentVO get(Long patientId, Long id)`
  - `MedicalDocumentVO create(Long patientId, MedicalDocumentDTO dto)`
  - `void delete(Long patientId, Long id)`
- 默认 limit=50，最大 200，非法按默认。
- `title` blank → null；超 128 → `标题过长`。
- `occurredAt` 晚于 `LocalDateTime.now().plusDays(1)` → `资料时间不合法`。
- 未知 `docType` → `不支持的资料类型`。
- 每条路径先 `patientAccess.requireAccessible(patientId)`。
- create：`setUploadedByUserId(UserContext.getUserId())`；userId 为空 → `未登录`。
- 不存在 → `就医资料不存在`。

- [ ] **Step 1: Write the failing test**

结构照 `HealthMetricRecordServiceImplTest`：mock repository + `PatientAccessService`，`UserContext.setUserId(11L)`。

必须覆盖：

1. `create` 写入 `patientId=3`、`uploadedByUserId=11`、`filesJson` 无 query；返回的 `docTypeName=报告单`、`fileCount=1`。
2. `create` 在 `requireAccessible` 抛「无权访问该患者」时不 insert。
3. `counts` 对缺失类型补 0。
4. `delete` 调用 `softDeleteByIdAndPatientId`；mapper 返回 0 时抛「就医资料不存在」。
5. 未知 docType 抛「不支持的资料类型」。

create 测试里 `when(mapper.insert(any())).thenAnswer(inv -> { entity.setId(9L); return 1; })`，随后 `selectByIdAndPatientId(9L, 3L)` 返回同一对象（补 `createdAt`）。

- [ ] **Step 2: Run test to verify it fails**

Run: `mvn -q -Dtest=PatientMedicalDocumentServiceImplTest test`

Expected: FAIL。

- [ ] **Step 3: Write service**

`PatientMedicalDocumentServiceImpl` 构造注入 `PatientMedicalDocumentRepository` 与 `PatientAccessService`。

`requireOwned`：accessible 后 `selectByIdAndPatientId`，null 则「就医资料不存在」。

`counts`：从 `MedicalDocumentType.values()` 循环，用 mapper 结果填 count。

- [ ] **Step 4: Run test to verify it passes**

Run: `mvn -q -Dtest=PatientMedicalDocumentServiceImplTest,MedicalDocumentFilesTest,MedicalDocumentTypeTest test`

Expected: PASS。

---

### Task 6: REST

**Files:**
- Create: `backend-java/src/main/java/com/wenrun/controller/PatientMedicalDocumentController.java`

**Interfaces:**
- 与 spec 第 6 节路径一致，返回 `Result<...>`，风格照 `HealthMetricRecordController`（controller 不重复鉴权，交给 service）。

```java
package com.wenrun.controller;

import com.wenrun.common.Result;
import com.wenrun.dto.MedicalDocumentDTO;
import com.wenrun.service.PatientMedicalDocumentService;
import com.wenrun.vo.MedicalDocumentCountVO;
import com.wenrun.vo.MedicalDocumentVO;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequiredArgsConstructor
public class PatientMedicalDocumentController {

    private final PatientMedicalDocumentService patientMedicalDocumentService;

    @GetMapping("/api/patients/{patientId}/medical-documents/counts")
    public Result<List<MedicalDocumentCountVO>> counts(@PathVariable Long patientId) {
        return Result.success(patientMedicalDocumentService.counts(patientId));
    }

    @GetMapping("/api/patients/{patientId}/medical-documents")
    public Result<List<MedicalDocumentVO>> list(@PathVariable Long patientId,
                                                @RequestParam(required = false) String docType,
                                                @RequestParam(required = false) Integer limit) {
        return Result.success(patientMedicalDocumentService.list(patientId, docType, limit));
    }

    @GetMapping("/api/patients/{patientId}/medical-documents/{id}")
    public Result<MedicalDocumentVO> get(@PathVariable Long patientId, @PathVariable Long id) {
        return Result.success(patientMedicalDocumentService.get(patientId, id));
    }

    @PostMapping("/api/patients/{patientId}/medical-documents")
    public Result<MedicalDocumentVO> create(@PathVariable Long patientId,
                                            @RequestBody MedicalDocumentDTO dto) {
        return Result.success(patientMedicalDocumentService.create(patientId, dto));
    }

    @DeleteMapping("/api/patients/{patientId}/medical-documents/{id}")
    public Result<Void> delete(@PathVariable Long patientId, @PathVariable Long id) {
        patientMedicalDocumentService.delete(patientId, id);
        return Result.success();
    }
}
```

注意：`/counts` 必须写在 `/{id}` 之前，避免 `counts` 被当成 id。上面把 counts 做成独立路径，list 是集合路径，没有冲突。

- [ ] **Step 1: 添加 controller**

- [ ] **Step 2: 跑后端测试**

Run: `mvn -q test`（在 `backend-java/`）

Expected: 退出码 0。

---

### Task 7: 前端 API 与纯函数

**Files:**
- Create: `frontend/src/features/archive/documents.js`
- Create: `frontend/src/api/modules/medicalDocument.js`
- Modify: `frontend/src/api/modules/index.js`
- Modify: `frontend/src/features/archive/tabs.js`
- Test: `frontend/test/medical-document.test.js`

**Interfaces:**
- `DOC_TYPES = [{ id: 'MEDICAL_RECORD', label: '病历', icon: 'record', tone: 'blue' }, { id: 'LAB_REPORT', label: '报告单', icon: 'clipboard', tone: 'green' }, { id: 'MEDICATION', label: '药物', icon: 'pill', tone: 'violet' }, { id: 'CHECKUP', label: '体检报告', icon: 'shield', tone: 'amber' }]`
- `canonicalFileUrl(raw)`：去 `?` 和 `#`；非 http(s) 返回 `''`
- `countByType(counts, typeId)`：`counts` 是 `{ docType, count }[]`，找不到返回 0
- `archiveDocTypeFromQuery(docType)`：合法四类原样返回，否则 `''`
- API：
  - `listMedicalDocumentCounts(patientId)`
  - `listMedicalDocuments(patientId, { docType, limit } = {})`
  - `createMedicalDocument(patientId, data)`
  - `deleteMedicalDocument(patientId, id)`
- `index.js` 增加 `export * from './medicalDocument'`
- `tabs.js` 增加 `export function archiveDocTypeFromQuery(docType) { return DOC_TYPES.some(...) ? docType : '' }`。为避免循环依赖，合法 id 数组可写在 `tabs.js` 本地 `['MEDICAL_RECORD', ...]`，或从 `documents.js` 导入（`tabs.js` 不要反过来被 `documents.js` 导入）。

- [ ] **Step 1: Write the failing test**

`frontend/test/medical-document.test.js`：

```js
import test from 'node:test'
import assert from 'node:assert/strict'
import { canonicalFileUrl, countByType, DOC_TYPES } from '../src/features/archive/documents.js'
import { archiveDocTypeFromQuery } from '../src/features/archive/tabs.js'

test('DOC_TYPES has four archive categories', () => {
  assert.deepEqual(DOC_TYPES.map((item) => item.id), [
    'MEDICAL_RECORD', 'LAB_REPORT', 'MEDICATION', 'CHECKUP',
  ])
  assert.deepEqual(DOC_TYPES.map((item) => item.label), ['病历', '报告单', '药物', '体检报告'])
})

test('canonicalFileUrl strips query and rejects non-http', () => {
  assert.equal(
    canonicalFileUrl('https://bucket.cos.ap-guangzhou.myqcloud.com/a.jpg?q-sign-algorithm=sha1'),
    'https://bucket.cos.ap-guangzhou.myqcloud.com/a.jpg',
  )
  assert.equal(canonicalFileUrl('javascript:alert(1)'), '')
})

test('countByType defaults missing types to zero', () => {
  assert.equal(countByType([{ docType: 'LAB_REPORT', count: 2 }], 'LAB_REPORT'), 2)
  assert.equal(countByType([{ docType: 'LAB_REPORT', count: 2 }], 'CHECKUP'), 0)
})

test('archiveDocTypeFromQuery only accepts four codes', () => {
  assert.equal(archiveDocTypeFromQuery('LAB_REPORT'), 'LAB_REPORT')
  assert.equal(archiveDocTypeFromQuery('OTHER'), '')
  assert.equal(archiveDocTypeFromQuery(), '')
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- test/medical-document.test.js`（在 `frontend/`）

Expected: FAIL，模块不存在。

- [ ] **Step 3: Implement helpers and API module**

`canonicalFileUrl`：

```js
export function canonicalFileUrl(raw) {
  const value = String(raw || '').trim()
  if (!/^https?:\/\//i.test(value)) return ''
  try {
    const url = new URL(value)
    url.search = ''
    url.hash = ''
    return url.toString().replace(/\/$/, (m, offset, s) => (url.pathname === '/' ? s : s.slice(0, -1)))
  } catch {
    return ''
  }
}
```

注意：`new URL` 对无 path 的 `https://x.com` 会得到 `https://x.com/`。COS 对象 URL 都有 path，保持 path 即可。更简单且与后端一致的做法：

```js
export function canonicalFileUrl(raw) {
  const value = String(raw || '').trim()
  if (!/^https?:\/\//i.test(value)) return ''
  try {
    const url = new URL(value)
    return `${url.protocol}//${url.host}${url.pathname || '/'}`
  } catch {
    return ''
  }
}
```

测试里的 COS 例子用这个实现即可。

API 文件照 `healthMetric.js`，路径：

- `GET /api/patients/${patientId}/medical-documents/counts`
- `GET /api/patients/${patientId}/medical-documents`
- `POST /api/patients/${patientId}/medical-documents`
- `DELETE /api/patients/${patientId}/medical-documents/${id}`

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- test/medical-document.test.js`

Expected: PASS。

---

### Task 8: 档案 UI 接上资料

**Files:**
- Create: `frontend/src/components/archive/ArchiveDocuments.vue`
- Modify: `frontend/src/views/PatientArchive.vue`
- Modify: `frontend/src/components/archive/ArchiveHealthData.vue`
- Modify: `frontend/src/components/archive/ArchiveSidebar.vue`
- Modify: `frontend/test/archive.test.js`

**Interfaces:**
- `ArchiveDocuments` props：`documents`（array）、`counts`、`error`、`saving`、`message`、`initialType`
- emits：`create`（payload）、`remove`（id）、`filter`（docType 或 `''`）
- `PatientArchive.load` 增加 `listMedicalDocumentCounts(activePatientId)` 与 `listMedicalDocuments(activePatientId)`，失败只填 `docsError`，不空白整页。
- `showUnavailable` 不再用于就医资料。侧栏「上传就医资料」改为 `emit('open-tab', 'documents')`（或 `open-upload`）。打开 documents 时展示登记表单。
- 四宫格：`共 ${n} 份`，点击 `open-tab` 到 documents，可 `router.replace({ query: { tab: 'documents', docType: id } })`。
- `tab === 'documents'` 渲染 `ArchiveDocuments`，删除对该 Tab 的 `ArchiveUnavailable`。
- 运动睡眠、腰围、WHtR、「上传健康数据」文案「数据库还未设计」保留。

- [ ] **Step 1: 改 archive 测试**

在 `frontend/test/archive.test.js`：

- 现有「undesigned modules」断言改为：`PatientArchive.vue` **不**再包含就医资料那句 hint「病历、报告单、药物和体检报告需要独立的资料库。」
- 新增：`ArchiveHealthData.vue` 不含「共 0 份 · 数据库还未设计」；含 `共 {{` 或 `countByType` / `docCounts`。
- 新增：`ArchiveDocuments.vue` 存在且含「上传资料」或「登记资料」。
- 新增：`PatientArchive.vue` 含 `listMedicalDocuments`，不含 `ArchiveUnavailable` 用于 documents 的那段（断言 `v-else-if="tab === 'documents'"` 后面不是 `ArchiveUnavailable`）。

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- test/archive.test.js`

Expected: FAIL。

- [ ] **Step 3: Implement Vue**

`ArchiveDocuments.vue` 最小行为：

- 顶部「登记资料」表单：`docType` select（四类）、`title`、`occurredAt`（datetime-local）、可动态增减的文件行（`url`、`contentType` select、`originalName`）。提交前对每个 url 调 `canonicalFileUrl`，空地址拦截。
- 下面按 `DOC_TYPES` 分四块，每块列出该类型 documents（`item.docType === type.id`），展示 title 或「未命名」、时间、`fileCount`、每个 file 的 `<a :href="file.url" target="_blank">`、删除按钮。
- `initialType` 非空时滚动/高亮该类。

`ArchiveHealthData` 增加 prop `docCounts`（默认 `[]`），`docs` 改为基于 `DOC_TYPES`，`small` 文案 `共 ${countByType(docCounts, item.id)} 份`，点击 `emit('open-tab', 'documents', item.id)` 或单独 emit。父组件负责带 query。

`PatientArchive` 的 `openTab`：若第二个参数是类型，写入 `query.docType`。

登记提交：

```js
await createMedicalDocument(activePatientId.value, {
  docType: form.docType,
  title: form.title,
  occurredAt: form.occurredAt || null,
  files: form.files.map((file) => ({
    url: canonicalFileUrl(file.url),
    contentType: file.contentType,
    originalName: file.originalName,
    size: file.size || null,
  })),
})
```

删除：`confirm` 后 `deleteMedicalDocument`，再 `load()`。

样式用现有 archive-panel / metric-card / btn token，不引入新色板。文件 URL 输入框可说明「填写 COS 返回的地址，系统会去掉签名参数」。

- [ ] **Step 4: Run frontend tests**

Run: `npm test`（在 `frontend/`）

Expected: 全部通过。

- [ ] **Step 5: 回归后端**

Run: `mvn -q test`（在 `backend-java/`）

Expected: 退出码 0。

---

## Self-review

1. **Spec coverage:** 表、四类枚举、URL 去签、授权、counts/list/get/create/delete、前端四宫格与 Tab、测试命令均有对应任务。COS SDK、挂号关联、按页删除明确不在任务中。
2. **Placeholder scan:** 无 TBD；校验文案与路径写死。
3. **Type consistency:** `docType` 字符串与枚举 `name()` 一致；`filesJson` 仅 entity 使用；API/VO 使用 `files` 数组；上传人字段只在服务写入。
