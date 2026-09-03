# 挂号写能力地基加固 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在给 AI 开放任何挂号写能力之前，先把挂号链路的幂等、号源一致性、以及意图路由与工具能力的措辞矛盾三处地基补齐。

**Architecture:** 三项改动彼此独立，都不引入新的架构层。前两项在 Java 侧 `RegistrationServiceImpl` 内完成：幂等键复用已有的 `registration.idempotency_key` 列与唯一索引，检查点放在 `SELECT ... FOR UPDATE` 行锁之内；号源回补通过新增的条件状态更新 `updateStatusIfCurrent` 保证「一张单只回补一次」。第三项只改 Python 侧两个 system prompt 的文案，不动图结构、不加工具。

**Tech Stack:** Java 21 / Spring Boot / MyBatis / MySQL；JUnit 5 + Mockito；Python 3.13 / LangGraph 1.2 / pytest。

## Global Constraints

- **本仓库没有把 `mvnw` / `mvnw.cmd` 提交进来**（`backend-java/.mvn/wrapper/` 下只有 `maven-wrapper.properties`）。本机已安装 Maven 3.9.9，系统 PATH 含 `D:\apache-maven-3.9.9\bin`，命令直接用 `mvn`。
  Maven 命令一律在 `backend-java/` 目录下执行，并带 `-o`（离线，依赖已在 `~/.m2/repository`）。新开的终端才能读到这次 PATH 变更；当前 Cursor 会话若仍找不到 `mvn`，先重启终端。
- Python 命令一律在 `ai-python/` 目录下执行，用 `python -m pytest`。
- 数据库不需要任何变更。`registration.idempotency_key` 列、`uk_registration_idempotency_key` 唯一索引、mapper 的 `insert`（已含该列）、`selectByIdempotencyKey` 都已经存在（见 `docs/SQL/schema.sql:141` 与 `:146`、`docs/SQL/migrations/2026-08-16-registration-idempotency.sql`）。**不要新建 migration。**
- 本计划不新增任何写工具、不改委托令牌 scope、不改 LangGraph 图结构。这些属于后续的写能力方案，见文末「不在本计划范围内」。
- 中文错误文案与既有风格保持一致（`BusinessException("...")`，不带句号）。
- 每个 Task 结束时单独提交一次。

## File Structure

| 文件 | 动作 | 职责 |
|---|---|---|
| `backend-java/src/main/java/com/wenrun/dto/RegistrationCreateDTO.java` | 修改 | 增加可选的 `idempotencyKey` 入参 |
| `backend-java/src/main/java/com/wenrun/service/impl/RegistrationServiceImpl.java` | 修改 | 幂等命中判定、号源回补、条件状态流转 |
| `backend-java/src/main/java/com/wenrun/repository/RegistrationRepository.java` | 修改 | 新增 `updateStatusIfCurrent` |
| `backend-java/src/main/resources/mapper/RegistrationRepository.xml` | 修改 | 新增 `updateStatusIfCurrent` 的 SQL |
| `backend-java/src/test/java/com/wenrun/service/impl/RegistrationServiceImplTest.java` | 修改 | Task 1、2 的全部测试 |
| `ai-python/app/graphs/hospital/nodes/begin.py` | 修改 | tools 标签描述与实际能力对齐 |
| `ai-python/app/graphs/hospital/nodes/tool.py` | 修改 | 把「拒绝挂号」改成「查清号源并引导」 |
| `ai-python/tests/unit/test_begin_node.py` | 修改 | prompt 契约测试 |
| `ai-python/tests/unit/test_tool_node.py` | 修改 | prompt 契约测试 |

---

### Task 1: 接上挂号幂等键

**背景：** `Registration` 实体有 `idempotencyKey` 字段、mapper 的 `insert` 语句里已经列了 `idempotency_key`、`selectByIdempotencyKey` 也写好了，但 `RegistrationServiceImpl.register()` 从头到尾没有读也没有写这个字段，DTO 上更没有入参。结果是这套幂等设施完全悬空，insert 时该列永远是 `NULL`。

**设计要点（务必按这个顺序，否则语义会错）：**

1. 幂等命中检查放在 `scheduleMapper.selectByIdForUpdate(...)` **之后**。行锁把同一排班的并发挂号请求串行化，锁内查询能读到前一笔已提交的记录，因此不需要额外的分布式锁。
2. 幂等命中要早于过期、号源、重复三项校验。否则一张已经挂成功的号在排班过期后被重放，会返回「该排班已过期」而不是原单号。
3. 唯一索引作为最后兜底：同一幂等键指向**不同** `scheduleId` 时锁的是不同的行，行锁挡不住，靠 `uk_registration_idempotency_key` 拦下，捕获 `DuplicateKeyException` 转成友好报错。
4. 空白字符串必须归一化成 `null`，否则多张单会共用 `''` 撞唯一索引。

**Files:**
- Modify: `backend-java/src/main/java/com/wenrun/dto/RegistrationCreateDTO.java`
- Modify: `backend-java/src/main/java/com/wenrun/service/impl/RegistrationServiceImpl.java:69-110`
- Test: `backend-java/src/test/java/com/wenrun/service/impl/RegistrationServiceImplTest.java`

**Interfaces:**
- Consumes: 已存在的 `RegistrationRepository.selectByIdempotencyKey(String)` 返回 `Registration`（可能为 `null`）；已存在的 `RegistrationRepository.insert(Registration)` 返回 `int`。
- Produces: `RegistrationCreateDTO.getIdempotencyKey()` / `setIdempotencyKey(String)`；`RegistrationServiceImpl.register(dto)` 在幂等命中时返回**已有**挂号单 id，且不扣号源、不 insert。

- [ ] **Step 1: 给 DTO 加上幂等键字段**

`backend-java/src/main/java/com/wenrun/dto/RegistrationCreateDTO.java` 整个替换为：

```java
package com.wenrun.dto;

import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import lombok.Data;

@Data
public class RegistrationCreateDTO {
    @NotNull
    private Long patientId;
    @NotNull
    private Long scheduleId;
    /** 幂等键，重放同一个键只会产生一张挂号单。长度与 registration.idempotency_key 对齐。 */
    @Size(max = 128)
    private String idempotencyKey;
}
```

- [ ] **Step 2: 写失败的测试**

在 `RegistrationServiceImplTest.java` 里，先把 import 区补全（在已有 import 之后追加）：

```java
import com.wenrun.entity.Registration;
import org.mockito.ArgumentCaptor;
import org.springframework.dao.DuplicateKeyException;

import static org.junit.jupiter.api.Assertions.assertNull;
import static org.mockito.ArgumentMatchers.any;
```

然后在类末尾追加这 6 个测试：

```java
    private Schedule bookableSchedule() {
        Schedule schedule = new Schedule();
        schedule.setId(9L);
        schedule.setStaffId(8L);
        schedule.setDeptId(3L);
        schedule.setWorkDate(clinic.today().plusDays(1));
        schedule.setTimePeriod("下午");
        schedule.setRemainingCount(19);
        return schedule;
    }

    private void givenPatientAndSchedule(Schedule schedule) {
        Patient patient = new Patient();
        patient.setId(1L);
        when(patientMapper.selectById(1L)).thenReturn(patient);
        when(scheduleMapper.selectByIdForUpdate(9L)).thenReturn(schedule);
    }

    private RegistrationCreateDTO dtoWithKey(String idempotencyKey) {
        RegistrationCreateDTO dto = new RegistrationCreateDTO();
        dto.setPatientId(1L);
        dto.setScheduleId(9L);
        dto.setIdempotencyKey(idempotencyKey);
        return dto;
    }

    @Test
    void registerReturnsExistingOrderWhenIdempotencyKeyIsReplayed() {
        givenPatientAndSchedule(bookableSchedule());
        Registration existing = new Registration();
        existing.setId(77L);
        existing.setPatientId(1L);
        when(registrationMapper.selectByIdempotencyKey("ai-reg-001")).thenReturn(existing);

        assertEquals(77L, service.register(dtoWithKey("ai-reg-001")));

        verify(scheduleMapper, never()).decrementRemaining(anyLong());
        verify(registrationMapper, never()).insert(any());
    }

    @Test
    void registerReplaysSuccessfullyEvenAfterScheduleExpired() {
        Schedule expired = bookableSchedule();
        expired.setWorkDate(clinic.today().minusDays(2));
        givenPatientAndSchedule(expired);
        Registration existing = new Registration();
        existing.setId(77L);
        existing.setPatientId(1L);
        when(registrationMapper.selectByIdempotencyKey("ai-reg-001")).thenReturn(existing);

        assertEquals(77L, service.register(dtoWithKey("ai-reg-001")));
    }

    @Test
    void registerRejectsIdempotencyKeyOwnedByAnotherPatient() {
        givenPatientAndSchedule(bookableSchedule());
        Registration other = new Registration();
        other.setId(77L);
        other.setPatientId(2L);
        when(registrationMapper.selectByIdempotencyKey("ai-reg-001")).thenReturn(other);

        BusinessException error = assertThrows(
                BusinessException.class, () -> service.register(dtoWithKey("ai-reg-001")));

        assertEquals("幂等键已被占用，请更换后重试", error.getMessage());
        verify(scheduleMapper, never()).decrementRemaining(anyLong());
    }

    @Test
    void registerPersistsIdempotencyKeyOnInsert() {
        givenPatientAndSchedule(bookableSchedule());
        when(scheduleMapper.decrementRemaining(9L)).thenReturn(1);
        ArgumentCaptor<Registration> saved = ArgumentCaptor.forClass(Registration.class);

        service.register(dtoWithKey("ai-reg-001"));

        verify(registrationMapper).insert(saved.capture());
        assertEquals("ai-reg-001", saved.getValue().getIdempotencyKey());
    }

    @Test
    void registerTreatsBlankIdempotencyKeyAsAbsent() {
        givenPatientAndSchedule(bookableSchedule());
        when(scheduleMapper.decrementRemaining(9L)).thenReturn(1);
        ArgumentCaptor<Registration> saved = ArgumentCaptor.forClass(Registration.class);

        service.register(dtoWithKey("   "));

        verify(registrationMapper, never()).selectByIdempotencyKey(org.mockito.ArgumentMatchers.anyString());
        verify(registrationMapper).insert(saved.capture());
        assertNull(saved.getValue().getIdempotencyKey());
    }

    @Test
    void registerTranslatesUniqueIndexViolationIntoBusinessError() {
        givenPatientAndSchedule(bookableSchedule());
        when(scheduleMapper.decrementRemaining(9L)).thenReturn(1);
        when(registrationMapper.insert(any()))
                .thenThrow(new DuplicateKeyException("uk_registration_idempotency_key"));

        BusinessException error = assertThrows(
                BusinessException.class, () -> service.register(dtoWithKey("ai-reg-001")));

        assertEquals("请勿重复提交挂号请求", error.getMessage());
    }
```

- [ ] **Step 3: 跑测试确认失败**

```powershell
mvn -o test "-Dtest=RegistrationServiceImplTest"
```

预期：`BUILD FAILURE`，`Tests run: 8, Failures: ..., Errors: ...`。`registerReturnsExistingOrderWhenIdempotencyKeyIsReplayed` 会因为服务端根本没查幂等键而走到正常挂号流程、返回 `null` 而非 `77`。

- [ ] **Step 4: 实现幂等逻辑**

在 `RegistrationServiceImpl.java` 的 import 区追加：

```java
import org.springframework.dao.DuplicateKeyException;

import java.util.Objects;
```

把 `register` 方法整体替换为：

```java
    // 挂号
    @Override
    @Transactional
    public Long register(RegistrationCreateDTO dto) {
        Long patientId = dto.getPatientId();
        if (AccountType.PATIENT.equals(UserContext.getAccountType())) {
            patientId = currentPatientId();
        }
        Patient patient = patientMapper.selectById(patientId);
        if (patient == null) {
            throw new BusinessException("患者不存在");
        }
        Schedule schedule = scheduleMapper.selectByIdForUpdate(dto.getScheduleId());
        if (schedule == null) {
            throw new BusinessException("排班不存在");
        }

        // 行锁已把同一排班的并发挂号串行化，锁内查询能读到前一笔已提交的重放记录。
        // 幂等命中必须早于过期与号源校验：已经挂上的号在排班过期后被重放时，应当返回原单而不是报错。
        String idempotencyKey = normalizeIdempotencyKey(dto.getIdempotencyKey());
        if (idempotencyKey != null) {
            Registration replayed = registrationMapper.selectByIdempotencyKey(idempotencyKey);
            if (replayed != null) {
                if (!Objects.equals(replayed.getPatientId(), patientId)) {
                    throw new BusinessException("幂等键已被占用，请更换后重试");
                }
                return replayed.getId();
            }
        }

        if (clinicProperties.isExpired(schedule.getWorkDate(), schedule.getTimePeriod())) {
            throw new BusinessException("该排班已过期，无法挂号");
        }
        if (schedule.getRemainingCount() == null || schedule.getRemainingCount() <= 0) {
            throw new BusinessException("号源已满");
        }
        if (registrationMapper.countActiveByPatientAndSlot(
                patientId, schedule.getStaffId(), schedule.getWorkDate(), schedule.getTimePeriod()) > 0) {
            throw new BusinessException("您已预约该医生此时段，不能重复挂号");
        }
        int updated = scheduleMapper.decrementRemaining(schedule.getId());
        if (updated == 0) {
            throw new BusinessException("号源扣减失败，请重试");
        }
        Registration reg = new Registration();
        reg.setRegNo(BizNoUtil.next("REG"));
        reg.setPatientId(patientId);
        reg.setScheduleId(schedule.getId());
        reg.setDeptId(schedule.getDeptId());
        reg.setStaffId(schedule.getStaffId());
        reg.setRegTime(LocalDateTime.now());
        reg.setRegFee(schedule.getRegisterFee());
        reg.setStatus(BizStatus.REG_REGISTERED);
        reg.setCashierId(UserContext.getUserId());
        reg.setRegistrantUserId(UserContext.getUserId());
        reg.setIdempotencyKey(idempotencyKey);
        try {
            registrationMapper.insert(reg);
        } catch (DuplicateKeyException ex) {
            // 同一幂等键指向不同排班时锁的不是同一行，行锁挡不住，由唯一索引兜底。
            throw new BusinessException("请勿重复提交挂号请求");
        }
        return reg.getId();
    }

    /** 空白幂等键归一化为 null，避免多张单共用空串撞唯一索引。 */
    private static String normalizeIdempotencyKey(String raw) {
        if (raw == null) {
            return null;
        }
        String trimmed = raw.trim();
        return trimmed.isEmpty() ? null : trimmed;
    }
```

- [ ] **Step 5: 跑测试确认通过**

```powershell
mvn -o test "-Dtest=RegistrationServiceImplTest"
```

预期：`BUILD SUCCESS`，`Tests run: 8, Failures: 0, Errors: 0, Skipped: 0`。

- [ ] **Step 6: 提交**

```powershell
git add backend-java/src/main/java/com/wenrun/dto/RegistrationCreateDTO.java backend-java/src/main/java/com/wenrun/service/impl/RegistrationServiceImpl.java backend-java/src/test/java/com/wenrun/service/impl/RegistrationServiceImplTest.java
git commit -m "fix(registration): 接上悬空的挂号幂等键，重放同一键只产生一张单"
```

---

### Task 2: 过期自动退号回补号源，并把状态流转改为条件更新

**背景：** `RegistrationServiceImpl.list()` 会把过期的「已挂号」惰性改成「已退号」，但没有像 `cancel()` 那样调用 `incrementRemaining`，`schedule.remaining_count` 会慢慢和实际有效挂号数对不上。同时这段写操作发生在一个没有事务的 GET 里，两个并发查询会各自把同一张单退一遍；`cancel()` 也是「先 select 判断、再无条件 update」，并发下同样会把号源加两次。

**设计要点：** 新增 `updateStatusIfCurrent(id, expectedStatus, status)`，用 `WHERE id = ? AND status = ?` 让状态流转本身成为并发的仲裁点——只有返回 1 的那一次才有资格回补号源。`list()` 补上 `@Transactional`。

**Files:**
- Modify: `backend-java/src/main/java/com/wenrun/repository/RegistrationRepository.java`
- Modify: `backend-java/src/main/resources/mapper/RegistrationRepository.xml:39-41`
- Modify: `backend-java/src/main/java/com/wenrun/service/impl/RegistrationServiceImpl.java:35-65,112-132`
- Test: `backend-java/src/test/java/com/wenrun/service/impl/RegistrationServiceImplTest.java`

**Interfaces:**
- Produces: `RegistrationRepository.updateStatusIfCurrent(Long id, Integer expectedStatus, Integer status)` 返回 `int` 受影响行数（0 或 1）。
- 保留：既有的无条件 `updateStatus(Long, Integer)` 不删除，`VisitServiceImpl.java:104` 还在用它把挂号单置为「已就诊」。

- [ ] **Step 1: 写失败的测试**

在 `RegistrationServiceImplTest.java` 的 import 区追加：

```java
import com.wenrun.vo.RegistrationVO;

import java.util.List;
```

在类末尾追加这 5 个测试（`LocalDate` 已在文件顶部导入）：

```java
    private RegistrationVO registeredVO(LocalDate workDate) {
        RegistrationVO vo = new RegistrationVO();
        vo.setId(55L);
        vo.setScheduleId(9L);
        vo.setStatus(BizStatus.REG_REGISTERED);
        vo.setWorkDate(workDate);
        vo.setTimePeriod("上午");
        return vo;
    }

    @Test
    void listReleasesSeatWhenExpiredRegistrationIsAutoCancelled() {
        RegistrationVO expired = registeredVO(clinic.today().minusDays(1));
        when(registrationMapper.selectList(1L, null, null, null, null))
                .thenReturn(List.of(expired));
        when(registrationMapper.updateStatusIfCurrent(
                55L, BizStatus.REG_REGISTERED, BizStatus.REG_CANCELLED)).thenReturn(1);

        List<RegistrationVO> result = service.list(1L, null, null, null, null);

        assertEquals(BizStatus.REG_CANCELLED, result.get(0).getStatus());
        verify(scheduleMapper).incrementRemaining(9L);
    }

    @Test
    void listDoesNotReleaseSeatWhenAnotherRequestAlreadyCancelled() {
        RegistrationVO expired = registeredVO(clinic.today().minusDays(1));
        when(registrationMapper.selectList(1L, null, null, null, null))
                .thenReturn(List.of(expired));
        when(registrationMapper.updateStatusIfCurrent(
                55L, BizStatus.REG_REGISTERED, BizStatus.REG_CANCELLED)).thenReturn(0);

        service.list(1L, null, null, null, null);

        verify(scheduleMapper, never()).incrementRemaining(anyLong());
    }

    @Test
    void listLeavesUnexpiredRegistrationUntouched() {
        RegistrationVO upcoming = registeredVO(clinic.today().plusDays(1));
        when(registrationMapper.selectList(1L, null, null, null, null))
                .thenReturn(List.of(upcoming));

        List<RegistrationVO> result = service.list(1L, null, null, null, null);

        assertEquals(BizStatus.REG_REGISTERED, result.get(0).getStatus());
        verify(registrationMapper, never())
                .updateStatusIfCurrent(anyLong(), org.mockito.ArgumentMatchers.anyInt(), org.mockito.ArgumentMatchers.anyInt());
        verify(scheduleMapper, never()).incrementRemaining(anyLong());
    }

    @Test
    void cancelReleasesSeatWhenStatusTransitionWins() {
        Registration reg = new Registration();
        reg.setId(55L);
        reg.setPatientId(1L);
        reg.setScheduleId(9L);
        reg.setStatus(BizStatus.REG_REGISTERED);
        when(registrationMapper.selectById(55L)).thenReturn(reg);
        when(registrationMapper.updateStatusIfCurrent(
                55L, BizStatus.REG_REGISTERED, BizStatus.REG_CANCELLED)).thenReturn(1);

        service.cancel(55L);

        verify(scheduleMapper).incrementRemaining(9L);
    }

    @Test
    void cancelRejectsWhenStatusChangedConcurrently() {
        Registration reg = new Registration();
        reg.setId(55L);
        reg.setPatientId(1L);
        reg.setScheduleId(9L);
        reg.setStatus(BizStatus.REG_REGISTERED);
        when(registrationMapper.selectById(55L)).thenReturn(reg);
        when(registrationMapper.updateStatusIfCurrent(
                55L, BizStatus.REG_REGISTERED, BizStatus.REG_CANCELLED)).thenReturn(0);

        BusinessException error = assertThrows(BusinessException.class, () -> service.cancel(55L));

        assertEquals("挂号单状态已变化，请刷新后重试", error.getMessage());
        verify(scheduleMapper, never()).incrementRemaining(anyLong());
    }
```

- [ ] **Step 2: 跑测试确认失败**

```powershell
mvn -o test "-Dtest=RegistrationServiceImplTest"
```

预期：编译失败，`cannot find symbol: method updateStatusIfCurrent`。

- [ ] **Step 3: 给 Repository 加条件更新方法**

在 `RegistrationRepository.java` 的 `updateStatus` 声明下方插入：

```java
    /** 仅当当前状态等于 expectedStatus 时才流转；返回受影响行数，用于判断本次调用是否真正生效。 */
    int updateStatusIfCurrent(@Param("id") Long id,
                              @Param("expectedStatus") Integer expectedStatus,
                              @Param("status") Integer status);
```

- [ ] **Step 4: 加对应的 SQL**

在 `RegistrationRepository.xml` 的 `<update id="updateStatus">` 之后插入：

```xml
    <update id="updateStatusIfCurrent">
        UPDATE registration SET status = #{status}
        WHERE id = #{id} AND status = #{expectedStatus}
    </update>
```

- [ ] **Step 5: 改 `list()`：补事务、条件流转、回补号源**

把 `RegistrationServiceImpl.list()` 整体替换为：

```java
    //获取用户挂号的信息
    @Override
    @Transactional
    public List<RegistrationVO> list(Long patientId, Long userId, Long registrantUserId, Long staffId, Integer status) {

        // 患者端的数据范围由登录态决定，不能信任前端传入的 patientId/userId。
        if (AccountType.PATIENT.equals(UserContext.getAccountType())) {
            patientId = currentPatientId();
            userId = null;
            registrantUserId = null;
            staffId = null;
        }

        //获取患者所有的挂号记录
        List<RegistrationVO> registrationVOList = registrationMapper.selectList(
                patientId, userId, registrantUserId, staffId, status);

        //判断当前患者挂号是否过期,如果过期则自动退号并把号源还回排班
        for (RegistrationVO registrationVO : registrationVOList) {
            //只处理"已挂号"状态的记录
            if (registrationVO.getStatus() == null || registrationVO.getStatus() != BizStatus.REG_REGISTERED) {
                continue;
            }
            if (!clinicProperties.isExpired(registrationVO.getWorkDate(), registrationVO.getTimePeriod())) {
                continue;
            }
            // 条件更新让状态流转本身成为并发仲裁点：只有抢到这次流转的调用才回补号源，
            // 否则两个并发查询会把同一张单的号源加两次。
            boolean transitioned = registrationMapper.updateStatusIfCurrent(
                    registrationVO.getId(), BizStatus.REG_REGISTERED, BizStatus.REG_CANCELLED) == 1;
            if (transitioned && registrationVO.getScheduleId() != null) {
                scheduleMapper.incrementRemaining(registrationVO.getScheduleId());
            }
            registrationVO.setStatus(BizStatus.REG_CANCELLED);
        }

        return registrationVOList;
    }
```

- [ ] **Step 6: 改 `cancel()`：用条件更新作为真正的守卫**

把 `RegistrationServiceImpl.cancel()` 里最后两行

```java
        registrationMapper.updateStatus(id, BizStatus.REG_CANCELLED);
        scheduleMapper.incrementRemaining(reg.getScheduleId());
```

替换为：

```java
        // 前面的状态判断只为给出友好文案；真正的并发守卫是这次条件更新。
        if (registrationMapper.updateStatusIfCurrent(
                id, BizStatus.REG_REGISTERED, BizStatus.REG_CANCELLED) != 1) {
            throw new BusinessException("挂号单状态已变化，请刷新后重试");
        }
        scheduleMapper.incrementRemaining(reg.getScheduleId());
```

- [ ] **Step 7: 跑测试确认通过**

```powershell
mvn -o test "-Dtest=RegistrationServiceImplTest"
```

预期：`BUILD SUCCESS`，`Tests run: 13, Failures: 0, Errors: 0, Skipped: 0`。

- [ ] **Step 8: 跑整个 Java 测试套件，确认没有回归**

```powershell
mvn -o test
```

预期：`BUILD SUCCESS`。特别关注 `ScheduleServiceImplTest` 和 `AiToolControllerTest`（`AiToolController.listMyRegistrations` 走的就是改过的 `list()`）。

- [ ] **Step 9: 提交**

```powershell
git add backend-java/src/main/java/com/wenrun/repository/RegistrationRepository.java backend-java/src/main/resources/mapper/RegistrationRepository.xml backend-java/src/main/java/com/wenrun/service/impl/RegistrationServiceImpl.java backend-java/src/test/java/com/wenrun/service/impl/RegistrationServiceImplTest.java
git commit -m "fix(registration): 过期自动退号回补号源，状态流转改为条件更新防并发双写"
```

---

### Task 3: 收敛意图路由与工具能力的措辞矛盾

**背景：** `begin.py` 把「挂号、预约/取消」明确划给 tools，示例里还写着「"帮我挂号" → tools」；但 `tool.py` 的 system prompt 第一条禁令就是「不挂号、不取消挂号、不退号、不改排班」。患者说「帮我挂号」会被准确路由到 tools，然后被 tools 当场拒绝。

**设计取向：** 路由是对的，不要改路由——挂号请求本来就该由业务 Agent 接住。要改的是 tools 接住之后干什么：从「拒绝」改成「查清可选号源、列出来、告诉患者最后一步在挂号页面确认」。这样既消除矛盾，又不需要任何写工具，并且将来真加了写工具时这段引导话术可以平滑替换。

**Files:**
- Modify: `ai-python/app/graphs/hospital/nodes/begin.py:40-41`
- Modify: `ai-python/app/graphs/hospital/nodes/tool.py:22-47`
- Test: `ai-python/tests/unit/test_begin_node.py`, `ai-python/tests/unit/test_tool_node.py`

**Interfaces:**
- 不改任何函数签名。`BEGIN_SYSTEM_PROMPT`、`TOOL_SYSTEM_PROMPT` 两个模块级常量的**文本内容**变化，测试按内容断言。

- [ ] **Step 1: 写失败的 prompt 契约测试**

在 `ai-python/tests/unit/test_begin_node.py` 里，`test_begin_prompt_limits_knowledge_to_medical_topics` 之后追加：

```python
def test_begin_prompt_routes_registration_actions_to_tools():
    assert "“帮我挂号” → tools" in begin.BEGIN_SYSTEM_PROMPT
    assert "退号" in begin.BEGIN_SYSTEM_PROMPT
```

在 `ai-python/tests/unit/test_tool_node.py` 里，`test_tool_system_prompt_includes_beijing_clock` 之后追加：

```python
def test_tool_prompt_guides_registration_instead_of_flatly_refusing():
    prompt = tool_node_module.TOOL_SYSTEM_PROMPT

    # 旧的一刀切禁令会让被路由过来的挂号请求直接吃闭门羹。
    assert "不挂号、不取消挂号" not in prompt
    # 新行为：先查清号源与本人预约，再引导到挂号页面完成最后一步。
    assert "不直接提交挂号" in prompt
    assert "挂号页面" in prompt
```

- [ ] **Step 2: 跑测试确认失败**

```powershell
cd ai-python
python -m pytest tests/unit/test_begin_node.py::test_begin_prompt_routes_registration_actions_to_tools tests/unit/test_tool_node.py::test_tool_prompt_guides_registration_instead_of_flatly_refusing -v
```

预期：两个测试都 FAIL。`test_begin_prompt_routes_registration_actions_to_tools` 挂在 `assert "退号" in ...`（当前 `BEGIN_SYSTEM_PROMPT` 里只有「预约/取消」，没有「退号」二字）；`test_tool_prompt_guides_registration_instead_of_flatly_refusing` 挂在 `assert "不挂号、不取消挂号" not in prompt`。

- [ ] **Step 3: 修正 `begin.py` 的 tools 标签描述**

把 `begin.py` 里这两行

```
- tools：需要查询或改动医院实时业务数据。
  包括：本院当前开设了哪些科室、挂号、预约/取消、查号源、查某位医生或某天排班、查我的预约。
```

替换为：

```
- tools：需要本院实时业务数据，或患者要办挂号、退号这类院内业务。
  包括：本院当前开设了哪些科室、查号源、查某位医生或某天排班、查我的预约，
  以及“帮我挂号”“我要退号”这类办理请求（由业务 Agent 查清号源并引导患者完成）。
```

- [ ] **Step 4: 把 `tool.py` 的禁令改成引导**

在 `TOOL_SYSTEM_PROMPT` 的工作流部分，把第 5 条

```
5. 工具返回「暂时无法查询」或提示姓名、科室不对时，如实转达并请患者确认或稍后重试，不要编造数据。
```

替换为下面两条（原第 5 条降为第 6 条）：

```
5. 患者要挂号、改约或退号时：先用 list_schedules 查清可选号源，或用 list_my_registrations 查清本人现有预约，
   把结果清楚列给患者，再说明最后一步需要他自己在挂号页面确认。不要说自己已经挂上或已经退掉。
6. 工具返回「暂时无法查询」或提示姓名、科室不对时，如实转达并请患者确认或稍后重试，不要编造数据。
```

在「你不要做」部分，把

```
- 不挂号、不取消挂号、不退号、不改排班；这类写操作请患者到院或在挂号页面办理
```

替换为：

```
- 不直接提交挂号、退号、改期，也不改排班；你只负责查清信息并引导，最终确认由患者在挂号页面完成
```

- [ ] **Step 5: 跑 Python 测试确认通过**

```powershell
python -m pytest tests/unit -v
```

预期：全部 PASS。特别注意 `test_every_hospital_tool_is_mounted_and_documented` 会断言四个工具名都还在 `TOOL_SYSTEM_PROMPT` 里——Step 4 的改动保留了 `list_schedules` 和 `list_my_registrations`，`list_departments` 和 `list_doctors` 在工作流第 2 条里没动。

- [ ] **Step 6: 提交**

```powershell
cd ..
git add ai-python/app/graphs/hospital/nodes/begin.py ai-python/app/graphs/hospital/nodes/tool.py ai-python/tests/unit/test_begin_node.py ai-python/tests/unit/test_tool_node.py
git commit -m "fix(ai): 消除意图路由与业务 Agent 的措辞矛盾，挂号请求改为查号源并引导"
```

---

## 完成标准

- [ ] `mvn -o test` 全绿
- [ ] `python -m pytest tests/unit` 全绿（在 `ai-python/` 下）
- [ ] 三次提交各自独立，每次都能单独回滚

## 不在本计划范围内

下面这些属于后续的「AI 写能力」方案，等地基落地后再单独立项：

- 新增 `registrations:write` scope 与 `POST /api/internal/ai-tools/registrations`
- `HumanInTheLoopMiddleware` 接入、SSE 中断事件、resume 端点
- 验证 `AsyncShallowRedisSaver` 是否支持 interrupt/resume（不支持就换 `AsyncRedisSaver`）
- `tool_node` 里同步 `agent.invoke()` 阻塞 async 事件循环的问题
- 扩展只读工具（收费项目价格、我的费用清单、我的就诊与处方记录）——这些需要先核查 `/api/charges`、`/api/prescriptions`、`/api/visits` 现有的患者归属校验是否到位
- 把缺失的 `mvnw` / `mvnw.cmd` 补进仓库，消除对本机 Maven 缓存路径的依赖
