# AI 一句话挂号／退号（带确认）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 患者在助手里说一句「帮我挂明天下午张伟的号」或「把我明天那个号退了」，AI 查清号源后弹出一张带权威业务信息的确认卡片，患者点一次确认即完成挂号或退号。

**Architecture:** 写操作的暂停点放在 **Tool 内部的 `interrupt()`**（LangGraph 官方的 custom interrupt forms 模式），不使用 `HumanInTheLoopMiddleware`——因为确认卡片必须展示从 Java 查回来的权威号源信息，而中间件只能展示模型自己生成的工具入参。图拓扑一行不改：`tool_node` 里那个用 `agent.invoke()` 调用的嵌套 Agent 编译时 `checkpointer=None`，按 LangGraph 的「per-invocation」语义会继承父图的 checkpointer，单次调用内的 `interrupt()` 能穿透到父图。SSE 增加一种 `confirm` 事件表示「已暂停待确认」，并新增 `resume` 端点用 `Command(resume=...)` 续跑同一个 thread。Java 侧新增 `registrations:write` scope 与两个写端点，并把委托令牌身份桥接进 `UserContext`，让既有的患者归属校验继续生效。

**Tech Stack:** Java 21 / Spring Boot / MyBatis / MySQL；JUnit 5 + Mockito + MockRestServiceServer；Python 3.13 / LangChain 1.3.14 / LangGraph 1.2.10 / langgraph-checkpoint-redis 0.5.2 / pytest；Vue 3 + Vitest。

## Global Constraints

- **本仓库没有把 `mvnw` / `mvnw.cmd` 提交进来。** 本机已装 Maven 3.9.9，PATH 含 `D:\apache-maven-3.9.9\bin`，命令直接用 `mvn`。Maven 命令一律在 `backend-java/` 下执行并带 `-o`（离线，依赖已在 `~/.m2/repository`）。
- Python 命令一律在 `ai-python/` 下执行，用 `python -m pytest`。
- 前端命令一律在 `frontend/` 下执行，用 `npm run test`。
- **数据库不需要任何变更。** `registration.idempotency_key` 列与 `uk_registration_idempotency_key` 唯一索引已存在（`docs/SQL/schema.sql:141`、`:146`）。`RegistrationServiceImpl.register()` 已经会读写幂等键，`cancel()` 已经是 `updateStatusIfCurrent` 条件更新。**不要新建 migration，不要改这两个方法。**
- 中文错误文案与既有风格保持一致（`BusinessException("...")`、Python 里直接返回中文句子），不带句号的沿用不带句号。
- **幂等键绝不能由模型生成**，必须由工具用 `conversation_id + tool_call_id` 拼出来。确认后节点会整段重跑，`tool_call_id` 在重跑时保持不变，这正是幂等生效的前提。
- **写工具只在会话带 checkpointer 时挂载。** 实测确认：没有 checkpointer 时 `interrupt()` 不抛错，而是静默返回 `__interrupt__` 且工具不执行，会让 `final_reply` 为空并把 `/v1/chat/stream` 打成 500。快速模式（`fast_mode=true`）同样不挂写工具。
- 委托令牌 TTL 只有 5 分钟（`AI_DELEGATION_TTL`），患者盯着确认卡片犹豫几分钟很正常。**resume 请求必须重新签发委托令牌**；因为节点会整段重跑并读取本次请求注入的 runtime context，新令牌能自然生效。
- 每个 Task 结束时单独提交一次。

## File Structure

| 文件 | 动作 | 职责 |
|---|---|---|
| `backend-java/src/main/java/com/wenrun/ai/security/DelegationTokenService.java` | 修改 | 新增 `PATIENT_ASSISTANT_SCOPES` 常量，含 `registrations:write` |
| `backend-java/src/main/java/com/wenrun/ai/security/DelegatedToolAuthInterceptor.java` | 修改 | 把委托身份桥接进 `UserContext`，请求结束时清理 |
| `backend-java/src/main/java/com/wenrun/ai/controller/aiController.java` | 修改 | 用新 scope 常量；`confirm` 事件按终态处理；新增 `/chat/resume` |
| `backend-java/src/main/java/com/wenrun/ai/vo/AiRegistrationCreateRequest.java` | 新建 | AI 挂号入参，只有 `scheduleId` 与 `idempotencyKey` |
| `backend-java/src/main/java/com/wenrun/ai/vo/aiResumeRequest.java` | 新建 | 恢复请求入参 |
| `backend-java/src/main/java/com/wenrun/ai/controller/AiToolController.java` | 修改 | 新增挂号／退号写端点与写权限校验 |
| `backend-java/src/main/java/com/wenrun/ai/service/aiService.java` | 修改 | 新增 `streamResume` |
| `ai-python/app/services/java_tool_client.py` | 修改 | `_post`、`get_schedule`、`create_registration`、`cancel_registration`、`JavaToolBusinessError` |
| `ai-python/app/graphs/hospital/tools/context.py` | 修改 | 上下文补 `conversation_id` 与 `writes_enabled` |
| `ai-python/app/graphs/hospital/tools/registration_write.py` | 新建 | 两个带确认中断的写工具 |
| `ai-python/app/graphs/hospital/tools/__init__.py` | 修改 | 导出写工具 |
| `ai-python/app/graphs/hospital/nodes/tool.py` | 修改 | 可写 Agent 与可写 prompt，按上下文择一调用 |
| `ai-python/app/models/chat.py` | 修改 | 新增 `ChatResumeRequest` |
| `ai-python/app/api/routes/chat.py` | 修改 | 抽出事件生成器、发 `confirm`、新增 `/v1/chat/resume` |
| `frontend/src/api/modules/ai.js` | 修改 | `confirm` 事件分支与 `chatResume` |
| `frontend/src/composables/useAssistant.js` | 修改 | 挂起态、`confirmPending` / `rejectPending` |
| `frontend/src/views/Assistant.vue` | 修改 | 气泡内确认卡片 |
| `docs/AI模块开发与运维指南.md` | 修改 | SSE 协议表补 `confirm` |

各任务的测试文件：`DelegationTokenServiceTest.java`、`DelegatedToolAuthInterceptorTest.java`、`AiToolControllerTest.java`、`AiServiceTest.java`、`tests/unit/test_java_tool_client.py`、`tests/unit/test_registration_write_tools.py`（新建）、`tests/unit/test_tool_node.py`、`tests/test_app.py`、`frontend/test/ai.test.js`。

---

### Task 1: 把委托身份桥接进 UserContext，并签发写 scope

**背景：** `/api/internal/ai-tools/**` 在 `WebMvcConfig` 里被排除了 `AuthInterceptor`，只走 `DelegatedToolAuthInterceptor`，所以 `UserContext` 是空的。而 `RegistrationServiceImpl.register()` / `cancel()` 全靠 `UserContext.getAccountType()` 判断是不是患者本人：

- `register()`：`AccountType.PATIENT.equals(...)` 时才把 `patientId` 强制成本人；`cashierId`、`registrantUserId` 取 `UserContext.getUserId()`。
- `cancel()`：`AccountType.PATIENT.equals(...)` 时才校验 `reg.getPatientId().equals(currentPatientId())`。

不桥接就直接开写端点的后果是：操作人字段写成 `null`，**退号的本人归属校验整段失效**。所以这是写能力的前置条件，必须先做。

**Files:**
- Modify: `backend-java/src/main/java/com/wenrun/ai/security/DelegatedToolAuthInterceptor.java`
- Modify: `backend-java/src/main/java/com/wenrun/ai/security/DelegationTokenService.java`
- Modify: `backend-java/src/main/java/com/wenrun/ai/controller/aiController.java:125-135`
- Test: `backend-java/src/test/java/com/wenrun/ai/security/DelegatedToolAuthInterceptorTest.java`
- Test: `backend-java/src/test/java/com/wenrun/ai/security/DelegationTokenServiceTest.java`

**Interfaces:**
- Produces: `DelegationTokenService.PATIENT_ASSISTANT_SCOPES`，类型 `Set<String>`，内容为 `departments:read`、`schedules:read`、`staff:read`、`registrations:read`、`registrations:write`。Task 2 的端点靠其中的 `registrations:write` 放行。
- Produces: 进入 `/api/internal/ai-tools/**` 的请求线程上，`UserContext.getUserId()` 等于令牌的 `userId`，`UserContext.getAccountType()` 等于令牌的 `accountType`。

- [ ] **Step 1: 写失败的测试**

在 `DelegatedToolAuthInterceptorTest.java` 的 import 区追加：

```java
import com.wenrun.common.context.UserContext;

import static org.junit.jupiter.api.Assertions.assertNull;
```

把 `cleanContext` 改成同时清理两个上下文：

```java
    @AfterEach
    void cleanContext() {
        DelegatedToolContext.clear();
        UserContext.clear();
    }
```

在类末尾追加两个测试：

```java
    @Test
    void bridgesDelegatedIdentityIntoUserContextForBusinessServices() {
        MockHttpServletRequest request = new MockHttpServletRequest();
        String token = tokenService.issue(7L, "patient", 11L, Set.of("registrations:write"));
        request.addHeader("Authorization", "Bearer " + token);

        interceptor.preHandle(request, new MockHttpServletResponse(), new Object());

        assertEquals(7L, UserContext.getUserId());
        assertEquals("patient", UserContext.getAccountType());
    }

    @Test
    void clearsBridgedUserContextAfterCompletion() {
        MockHttpServletRequest request = new MockHttpServletRequest();
        String token = tokenService.issue(7L, "patient", 11L, Set.of("registrations:read"));
        request.addHeader("Authorization", "Bearer " + token);
        interceptor.preHandle(request, new MockHttpServletResponse(), new Object());

        interceptor.afterCompletion(request, new MockHttpServletResponse(), new Object(), null);

        assertNull(UserContext.getUserId());
        assertNull(UserContext.getAccountType());
    }
```

在 `DelegationTokenServiceTest.java` 的 import 区追加：

```java
import static org.junit.jupiter.api.Assertions.assertEquals;
```

（如果该 import 已存在就不用重复添加。）在类末尾追加：

```java
    @Test
    void patientAssistantScopesCoverReadsAndRegistrationWrites() {
        assertEquals(
                Set.of("departments:read", "schedules:read", "staff:read",
                        "registrations:read", "registrations:write"),
                DelegationTokenService.PATIENT_ASSISTANT_SCOPES);
    }
```

- [ ] **Step 2: 跑测试确认失败**

```powershell
mvn -o test "-Dtest=DelegatedToolAuthInterceptorTest+DelegationTokenServiceTest"
```

预期：编译失败，`cannot find symbol: variable PATIENT_ASSISTANT_SCOPES`。

- [ ] **Step 3: 加 scope 常量**

在 `DelegationTokenService.java` 的类体最上方（`issue` 方法之前）插入：

```java
    /**
     * 患者端助手会话签发的固定 scope。写能力只覆盖挂号与退号，不含改排班、不含他人数据。
     */
    public static final Set<String> PATIENT_ASSISTANT_SCOPES = Set.of(
            "departments:read",
            "schedules:read",
            "staff:read",
            "registrations:read",
            "registrations:write");
```

`java.util.Set` 已经被该文件导入（`issue` 的入参就是 `Set<String>`），不需要新增 import。

- [ ] **Step 4: 桥接 UserContext**

在 `DelegatedToolAuthInterceptor.java` 的 import 区追加：

```java
import com.wenrun.common.context.UserContext;
```

把 `preHandle` 的最后两行

```java
        DelegatedToolContext.set(delegationTokenService.verifyForToolApi(token));
        return true;
```

替换为：

```java
        DelegatedToolPrincipal principal = delegationTokenService.verifyForToolApi(token);
        DelegatedToolContext.set(principal);
        // 业务 Service 的「患者本人」校验读的是 UserContext，而这条路径不走 AuthInterceptor。
        // 不补这两行，退号的归属校验会整段失效，操作人字段也会写成 null。
        UserContext.setUserId(principal.userId());
        UserContext.setAccountType(principal.accountType());
        return true;
```

把 `afterCompletion` 的方法体替换为：

```java
        DelegatedToolContext.clear();
        UserContext.clear();
```

- [ ] **Step 5: 让助手会话签发写 scope**

在 `aiController.java` 的 import 区确认已有 `com.wenrun.ai.security.DelegationTokenService`（已存在），然后把 `prepare()` 里的

```java
        request.setDelegatedToken(
                delegationTokenService.issue(
                        request.getUserId(),
                        UserContext.getAccountType(),
                        request.getPatientId(),
                        Set.of(
                                "departments:read",
                                "schedules:read",
                                "staff:read",
                                "registrations:read")));
```

替换为：

```java
        request.setDelegatedToken(
                delegationTokenService.issue(
                        request.getUserId(),
                        UserContext.getAccountType(),
                        request.getPatientId(),
                        DelegationTokenService.PATIENT_ASSISTANT_SCOPES));
```

替换后 `java.util.Set` 在 `aiController.java` 里可能不再被使用，编译会报 unused import 警告但不会失败；如果 IDE 提示，删掉 `import java.util.Set;`。

- [ ] **Step 6: 跑测试确认通过**

```powershell
mvn -o test "-Dtest=DelegatedToolAuthInterceptorTest+DelegationTokenServiceTest+AiToolControllerTest"
```

预期：`BUILD SUCCESS`，三个测试类全绿。`AiToolControllerTest` 直接调 controller 方法、不经过拦截器，所以不受桥接影响。

- [ ] **Step 7: 提交**

```powershell
git add backend-java/src/main/java/com/wenrun/ai/security/DelegationTokenService.java backend-java/src/main/java/com/wenrun/ai/security/DelegatedToolAuthInterceptor.java backend-java/src/main/java/com/wenrun/ai/controller/aiController.java backend-java/src/test/java/com/wenrun/ai/security/DelegatedToolAuthInterceptorTest.java backend-java/src/test/java/com/wenrun/ai/security/DelegationTokenServiceTest.java
git commit -m "feat(ai): 委托令牌身份桥接进 UserContext，并签发 registrations:write"
```

---

### Task 2: AiToolController 开放挂号与退号写端点

**背景：** `AiToolController` 现在 10 个端点全是 GET。写端点的安全边界靠三层：scope 必须含 `registrations:write`；账号类型必须是 `patient`（内部账号、医生账号不允许通过助手替人挂号）；`patientId` 只取令牌里的，请求体根本没有这个字段。归属校验则由 Task 1 桥接后的 `UserContext` 驱动 `RegistrationServiceImpl` 内既有的逻辑完成。

**Files:**
- Create: `backend-java/src/main/java/com/wenrun/ai/vo/AiRegistrationCreateRequest.java`
- Modify: `backend-java/src/main/java/com/wenrun/ai/controller/AiToolController.java`
- Test: `backend-java/src/test/java/com/wenrun/ai/controller/AiToolControllerTest.java`

**Interfaces:**
- Consumes: `DelegationTokenService.PATIENT_ASSISTANT_SCOPES`（Task 1）里的 `registrations:write`。
- Consumes: 已存在的 `RegistrationService.register(RegistrationCreateDTO)` 返回 `Long`；`RegistrationService.cancel(Long)` 返回 `void`。
- Produces: `POST /api/internal/ai-tools/registrations`，请求体 `{"scheduleId": 9, "idempotencyKey": "..."}`，响应 `Result<Long>`（`data` 是挂号单 id）。
- Produces: `POST /api/internal/ai-tools/registrations/{id}/cancel`，无请求体，响应 `Result<Void>`。

- [ ] **Step 1: 写失败的测试**

在 `AiToolControllerTest.java` 的 import 区追加：

```java
import com.wenrun.ai.vo.AiRegistrationCreateRequest;
import com.wenrun.common.constant.AccountType;
import com.wenrun.dto.RegistrationCreateDTO;
import org.mockito.ArgumentCaptor;

import static org.mockito.ArgumentMatchers.any;
```

在类末尾追加这 6 个测试：

```java
    private AiRegistrationCreateRequest createRequest() {
        AiRegistrationCreateRequest body = new AiRegistrationCreateRequest();
        body.setScheduleId(9L);
        body.setIdempotencyKey("conversation-1:call-1");
        return body;
    }

    private void givenWritablePatientToken() {
        DelegatedToolContext.set(new DelegatedToolPrincipal(7L, 11L, AccountType.PATIENT,
                Set.of("registrations:write"), "token-1"));
    }

    @Test
    void createRegistrationForcesTokenPatientIdAndForwardsIdempotencyKey() {
        givenWritablePatientToken();
        when(registrationService.register(any())).thenReturn(55L);
        ArgumentCaptor<RegistrationCreateDTO> sent = ArgumentCaptor.forClass(RegistrationCreateDTO.class);

        assertEquals(55L, controller.createMyRegistration(createRequest()).getData());

        verify(registrationService).register(sent.capture());
        assertEquals(11L, sent.getValue().getPatientId());
        assertEquals(9L, sent.getValue().getScheduleId());
        assertEquals("conversation-1:call-1", sent.getValue().getIdempotencyKey());
    }

    @Test
    void cancelRegistrationDelegatesToBusinessService() {
        givenWritablePatientToken();

        controller.cancelMyRegistration(55L);

        verify(registrationService).cancel(55L);
    }

    @Test
    void writeEndpointsRejectReadOnlyToken() {
        DelegatedToolContext.set(new DelegatedToolPrincipal(7L, 11L, AccountType.PATIENT,
                Set.of("registrations:read"), "token-1"));

        assertThrows(BusinessException.class, () -> controller.createMyRegistration(createRequest()));
        assertThrows(BusinessException.class, () -> controller.cancelMyRegistration(55L));
        verifyNoInteractions(registrationService);
    }

    @Test
    void writeEndpointsRejectNonPatientAccount() {
        DelegatedToolContext.set(new DelegatedToolPrincipal(7L, 11L, AccountType.STAFF,
                Set.of("registrations:write"), "token-1"));

        assertThrows(BusinessException.class, () -> controller.createMyRegistration(createRequest()));
        assertThrows(BusinessException.class, () -> controller.cancelMyRegistration(55L));
        verifyNoInteractions(registrationService);
    }

    @Test
    void writeEndpointsRejectTokenWithoutPatientProfile() {
        DelegatedToolContext.set(new DelegatedToolPrincipal(7L, null, AccountType.PATIENT,
                Set.of("registrations:write"), "token-1"));

        assertThrows(BusinessException.class, () -> controller.createMyRegistration(createRequest()));
        assertThrows(BusinessException.class, () -> controller.cancelMyRegistration(55L));
        verifyNoInteractions(registrationService);
    }

    @Test
    void readEndpointsStillWorkWithoutWriteScope() {
        when(registrationService.list(11L, null, null, null, null)).thenReturn(List.of());
        DelegatedToolContext.set(new DelegatedToolPrincipal(7L, 11L, AccountType.PATIENT,
                Set.of("registrations:read"), "token-1"));

        controller.listMyRegistrations(null);

        verify(registrationService).list(11L, null, null, null, null);
    }
```

- [ ] **Step 2: 跑测试确认失败**

```powershell
mvn -o test "-Dtest=AiToolControllerTest"
```

预期：编译失败，`package com.wenrun.ai.vo does not exist` 或 `cannot find symbol: class AiRegistrationCreateRequest`。

- [ ] **Step 3: 新建写入参 DTO**

创建 `backend-java/src/main/java/com/wenrun/ai/vo/AiRegistrationCreateRequest.java`：

```java
package com.wenrun.ai.vo;

import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import lombok.Data;

/**
 * AI 代患者提交挂号的入参。
 * 故意不提供 patientId：患者维度只由委托令牌决定，Python 不能自选患者。
 */
@Data
public class AiRegistrationCreateRequest {

    @NotNull(message = "排班不能为空")
    private Long scheduleId;

    /** 幂等键，由 Python 用 会话 ID + 工具调用 ID 拼出，重放同一个键只会产生一张挂号单。 */
    @Size(max = 128, message = "幂等键长度不能超过 128 个字符")
    private String idempotencyKey;
}
```

- [ ] **Step 4: 加写端点**

在 `AiToolController.java` 的 import 区追加：

```java
import com.wenrun.ai.vo.AiRegistrationCreateRequest;
import com.wenrun.common.constant.AccountType;
import com.wenrun.dto.RegistrationCreateDTO;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
```

把类注释里的

```java
 * 但不暴露写操作，也不提供通用 SQL。
```

替换为：

```java
 * 写操作只开放挂号与退号两项，且仅限患者账号本人；不提供通用 SQL。
```

在 `listMyPendingRegistrations` 方法之后、`requireScope` 之前插入：

```java
    /** 为令牌所属患者挂号。真正的过期、号源、重复校验与幂等都在 RegistrationServiceImpl 里。 */
    @PostMapping("/registrations")
    public Result<Long> createMyRegistration(@Valid @RequestBody AiRegistrationCreateRequest body) {
        Long patientId = requireWritablePatientId();
        RegistrationCreateDTO dto = new RegistrationCreateDTO();
        dto.setPatientId(patientId);
        dto.setScheduleId(body.getScheduleId());
        dto.setIdempotencyKey(body.getIdempotencyKey());
        return Result.success(registrationService.register(dto));
    }

    /** 退号。挂号单归属由 RegistrationServiceImpl 依据桥接进来的 UserContext 校验。 */
    @PostMapping("/registrations/{id}/cancel")
    public Result<Void> cancelMyRegistration(@PathVariable Long id) {
        requireWritablePatientId();
        registrationService.cancel(id);
        return Result.success();
    }
```

在 `requirePatientId` 方法之后插入：

```java
    /**
     * 写操作的准入：必须有写 scope、必须是患者账号、必须绑定了患者档案。
     * 只有患者本人能通过助手办理，内部账号与医生账号一律走原有的柜台流程。
     */
    private Long requireWritablePatientId() {
        DelegatedToolPrincipal principal = DelegatedToolContext.getRequired();
        if (!principal.hasScope("registrations:write")) {
            throw new BusinessException(ResultCode.FORBIDDEN, "AI 委托令牌没有所需权限");
        }
        if (!AccountType.PATIENT.equals(principal.accountType())) {
            throw new BusinessException(ResultCode.FORBIDDEN, "只有患者本人可以通过助手办理挂号");
        }
        if (principal.patientId() == null) {
            throw new BusinessException(ResultCode.FORBIDDEN, "当前账号还没有绑定患者档案");
        }
        return principal.patientId();
    }
```

- [ ] **Step 5: 跑测试确认通过**

```powershell
mvn -o test "-Dtest=AiToolControllerTest"
```

预期：`BUILD SUCCESS`，`Tests run: 17, Failures: 0, Errors: 0, Skipped: 0`。

- [ ] **Step 6: 跑整个 Java 测试套件**

```powershell
mvn -o test
```

预期：`BUILD SUCCESS`。

- [ ] **Step 7: 提交**

```powershell
git add backend-java/src/main/java/com/wenrun/ai/vo/AiRegistrationCreateRequest.java backend-java/src/main/java/com/wenrun/ai/controller/AiToolController.java backend-java/src/test/java/com/wenrun/ai/controller/AiToolControllerTest.java
git commit -m "feat(ai): AI 工具接口开放本人挂号与退号写端点"
```

---

### Task 3: JavaToolClient 支持写请求与单条排班查询

**背景：** `JavaToolClient` 现在只有 `_get`。写工具需要三样新能力：按 id 查单条排班（用来渲染权威确认卡片，端点 `/api/internal/ai-tools/schedules/{id}` 早就存在）、提交挂号、提交退号。

另外现在业务失败被统一包成 `JavaToolClientError("Java Tool API rejected the request: 号源已满")`。写工具需要把「号源已满」这类中文文案原样转达给患者，所以要能区分「服务不可用」和「业务规则拒绝」。

**Files:**
- Modify: `ai-python/app/services/java_tool_client.py`
- Test: `ai-python/tests/unit/test_java_tool_client.py`

**Interfaces:**
- Produces: `JavaToolBusinessError(JavaToolClientError)`，`str(exc)` 就是 Java 返回的中文 message。
- Produces: `JavaToolClient.get_schedule(delegated_token, request_id, *, schedule_id: int) -> Schedule`
- Produces: `JavaToolClient.create_registration(delegated_token, request_id, *, schedule_id: int, idempotency_key: str) -> int`
- Produces: `JavaToolClient.cancel_registration(delegated_token, request_id, *, registration_id: int) -> None`

- [ ] **Step 1: 写失败的测试**

在 `tests/unit/test_java_tool_client.py` 的 import 区，把

```python
from app.services.java_tool_client import JavaToolClient, JavaToolClientError
```

替换为：

```python
from app.services.java_tool_client import (
    JavaToolBusinessError,
    JavaToolClient,
    JavaToolClientError,
)
```

在文件末尾追加：

```python
def test_get_schedule_reads_single_slot_by_id():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/api/internal/ai-tools/schedules/9"
        return httpx.Response(
            200,
            json=_envelope(
                {
                    "id": 9,
                    "deptName": "内科",
                    "staffName": "张伟",
                    "workDate": "2026-09-04",
                    "timePeriod": "下午",
                    "remainingCount": 3,
                    "registerFee": 50.0,
                }
            ),
        )

    schedule = _client(handler).get_schedule("delegated-token", "trace-123", schedule_id=9)

    assert schedule.staff_name == "张伟"
    assert schedule.remaining_count == 3
    assert schedule.register_fee == "50.0"


def test_create_registration_posts_schedule_and_idempotency_key():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/api/internal/ai-tools/registrations"
        assert request.headers["Authorization"] == "Bearer delegated-token"
        assert json.loads(request.content) == {
            "scheduleId": 9,
            "idempotencyKey": "conversation-1:call-1",
        }
        return httpx.Response(200, json=_envelope(55))

    registration_id = _client(handler).create_registration(
        "delegated-token",
        "trace-123",
        schedule_id=9,
        idempotency_key="conversation-1:call-1",
    )

    assert registration_id == 55


def test_create_registration_never_sends_a_patient_id():
    def handler(request: httpx.Request) -> httpx.Response:
        assert "patientId" not in json.loads(request.content)
        return httpx.Response(200, json=_envelope(55))

    _client(handler).create_registration(
        "delegated-token", "trace-123", schedule_id=9, idempotency_key="key-1"
    )


def test_cancel_registration_posts_to_cancel_path():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/api/internal/ai-tools/registrations/55/cancel"
        return httpx.Response(200, json=_envelope(None))

    _client(handler).cancel_registration("delegated-token", "trace-123", registration_id=55)


def test_business_rejection_is_distinguishable_and_keeps_chinese_message():
    client = _client(
        lambda request: httpx.Response(200, json={"code": 400, "message": "号源已满"})
    )

    with pytest.raises(JavaToolBusinessError) as caught:
        client.create_registration(
            "delegated-token", "trace-123", schedule_id=9, idempotency_key="key-1"
        )

    assert str(caught.value) == "号源已满"
    assert isinstance(caught.value, JavaToolClientError)


def test_transport_failure_is_not_a_business_rejection():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    with pytest.raises(JavaToolClientError) as caught:
        _client(handler).create_registration(
            "delegated-token", "trace-123", schedule_id=9, idempotency_key="key-1"
        )

    assert not isinstance(caught.value, JavaToolBusinessError)
```

在该测试文件顶部的 import 区追加（`from datetime import date` 之前）：

```python
import json
```

- [ ] **Step 2: 跑测试确认失败**

```powershell
cd ai-python
python -m pytest tests/unit/test_java_tool_client.py -v
```

预期：collection 阶段就报 `ImportError: cannot import name 'JavaToolBusinessError'`。

- [ ] **Step 3: 加业务异常类型与请求信封解析**

在 `java_tool_client.py` 里，把

```python
class JavaToolClientError(RuntimeError):
    """Java Tool API 不可用、未授权或返回了不符合契约的数据。"""
```

替换为：

```python
class JavaToolClientError(RuntimeError):
    """Java Tool API 不可用、未授权或返回了不符合契约的数据。"""


class JavaToolBusinessError(JavaToolClientError):
    """Java 依据业务规则拒绝了本次请求，message 是可以直接转达给患者的中文文案。"""
```

- [ ] **Step 4: 抽出排班映射与信封解析，并加 `_post`**

在 `java_tool_client.py` 的 `_optional_str` 函数之后插入：

```python
def _to_schedule(item: dict[str, Any]) -> Schedule:
    return Schedule(
        id=_required_int(item, "id"),
        dept_name=_optional_str(item, "deptName"),
        staff_name=_optional_str(item, "staffName"),
        work_date=_optional_str(item, "workDate"),
        time_period=_optional_str(item, "timePeriod"),
        total_count=_optional_int(item, "totalCount"),
        remaining_count=_optional_int(item, "remainingCount"),
        register_fee=_optional_str(item, "registerFee"),
    )
```

把 `list_schedules` 方法体末尾的

```python
        return [
            Schedule(
                id=_required_int(item, "id"),
                dept_name=_optional_str(item, "deptName"),
                staff_name=_optional_str(item, "staffName"),
                work_date=_optional_str(item, "workDate"),
                time_period=_optional_str(item, "timePeriod"),
                total_count=_optional_int(item, "totalCount"),
                remaining_count=_optional_int(item, "remainingCount"),
                register_fee=_optional_str(item, "registerFee"),
            )
            for item in data
        ]
```

替换为：

```python
        return [_to_schedule(item) for item in data]
```

在 `list_schedules` 之后插入：

```python
    def get_schedule(
        self,
        delegated_token: str,
        request_id: str | None,
        *,
        schedule_id: int,
    ) -> Schedule:
        """按 id 查单条排班。确认卡片必须用这里查回来的权威数据，不能用模型复述的。"""
        data = self._get(
            f"/api/internal/ai-tools/schedules/{schedule_id}",
            delegated_token,
            request_id,
        )
        if not isinstance(data, dict):
            raise JavaToolClientError("Java Tool API returned an invalid schedule")
        return _to_schedule(data)
```

在 `list_my_registrations` 之后插入：

```python
    def create_registration(
        self,
        delegated_token: str,
        request_id: str | None,
        *,
        schedule_id: int,
        idempotency_key: str,
    ) -> int:
        """患者维度由 Java 依据委托令牌决定，这里不能也不该传 patientId。"""
        data = self._post(
            "/api/internal/ai-tools/registrations",
            delegated_token,
            request_id,
            {"scheduleId": schedule_id, "idempotencyKey": idempotency_key},
        )
        if not isinstance(data, int):
            raise JavaToolClientError("Java Tool API returned an invalid registration id")
        return data

    def cancel_registration(
        self,
        delegated_token: str,
        request_id: str | None,
        *,
        registration_id: int,
    ) -> None:
        self._post(
            f"/api/internal/ai-tools/registrations/{registration_id}/cancel",
            delegated_token,
            request_id,
            {},
        )
```

- [ ] **Step 5: 重写 `_get` 并新增 `_post`**

把文件末尾的 `_get` 方法整体替换为下面三个方法：

```python
    def _get(
        self,
        path: str,
        delegated_token: str,
        request_id: str | None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        headers = self._headers(delegated_token, request_id)
        query = {key: value for key, value in (params or {}).items() if value is not None}
        try:
            with httpx.Client(
                base_url=self._base_url,
                timeout=self._timeout,
                transport=self._transport,
            ) as client:
                response = client.get(path, headers=headers, params=query or None)
        except httpx.HTTPError as exc:
            raise JavaToolClientError("Java Tool API is unavailable") from exc
        return self._unwrap(response)

    def _post(
        self,
        path: str,
        delegated_token: str,
        request_id: str | None,
        payload: dict[str, Any],
    ) -> Any:
        headers = self._headers(delegated_token, request_id)
        try:
            with httpx.Client(
                base_url=self._base_url,
                timeout=self._timeout,
                transport=self._transport,
            ) as client:
                response = client.post(path, headers=headers, json=payload)
        except httpx.HTTPError as exc:
            raise JavaToolClientError("Java Tool API is unavailable") from exc
        return self._unwrap(response)

    def _headers(self, delegated_token: str, request_id: str | None) -> dict[str, str]:
        if not delegated_token.strip():
            raise JavaToolClientError("delegated token is missing")
        headers = {"Authorization": f"Bearer {delegated_token}"}
        if request_id:
            headers["X-Request-Id"] = request_id
        return headers

    def _unwrap(self, response: httpx.Response) -> Any:
        if response.status_code != 200:
            raise JavaToolClientError(f"Java Tool API returned HTTP {response.status_code}")
        try:
            body: dict[str, Any] = response.json()
        except (TypeError, ValueError) as exc:
            raise JavaToolClientError("Java Tool API returned invalid JSON") from exc
        if not isinstance(body, dict):
            raise JavaToolClientError("Java Tool API returned an invalid result envelope")
        # Java 的业务异常同样是 HTTP 200，只在信封里降级 code，必须单独判断。
        # 这里的 message 是给患者看的中文文案，原样保留，不加英文前缀。
        if body.get("code") != 200:
            raise JavaToolBusinessError(
                str(body.get("message") or body.get("code"))
            )
        return body.get("data")
```

- [ ] **Step 6: 跑测试确认通过**

```powershell
python -m pytest tests/unit/test_java_tool_client.py -v
```

预期：全部 PASS。原有的 `test_business_failure_inside_http_200_envelope_is_an_error` 仍然通过——`JavaToolBusinessError` 是 `JavaToolClientError` 的子类，且 message 里仍含「当前账号还没有绑定患者档案」。

- [ ] **Step 7: 提交**

```powershell
cd ..
git add ai-python/app/services/java_tool_client.py ai-python/tests/unit/test_java_tool_client.py
git commit -m "feat(ai): JavaToolClient 支持写请求、单条排班查询与业务异常区分"
```

---

### Task 4: 两个带确认中断的写工具

**背景：** 这是整个方案的核心。工具在提交前先从 Java 查回权威业务信息，用 `interrupt()` 把它作为确认卡片抛给前端；患者点确认后节点整段重跑，工具再次执行到 `interrupt()` 时直接拿到 resume 值继续往下走。

已实测验证的三条行为（用与本仓库一致的嵌套 Agent 结构）：确认前工具体的写调用不会执行；`approve` 后写调用只执行一次；`reject` 后完全不写。重跑时 `runtime.tool_call_id` 不变，所以幂等键稳定。

**设计要点：**

1. **幂等键用 `conversation_id + tool_call_id`。** 模型生成的键不可信，也不稳定。
2. **确认卡片的内容来自 Java，不来自模型。** 模型只提供 `schedule_id` / `registration_id` 这个「指针」，卡片上的科室、医生、日期、时段、费用全部由本工具查回来。
3. **resume 时会重查一次号源**，这是好事：患者犹豫期间号可能被别人抢走，重查能拿到最新余号，随后的 `register()` 还有行锁与 `decrementRemaining` 兜底。
4. **业务拒绝要原样转达。** `JavaToolBusinessError` 的中文文案直接拼进返回值给模型复述。

**Files:**
- Modify: `ai-python/app/graphs/hospital/tools/context.py`
- Create: `ai-python/app/graphs/hospital/tools/registration_write.py`
- Modify: `ai-python/app/graphs/hospital/tools/__init__.py`
- Test: `ai-python/tests/unit/test_registration_write_tools.py`（新建）

**Interfaces:**
- Consumes: `JavaToolClient.get_schedule` / `create_registration` / `cancel_registration` / `list_my_registrations`，`JavaToolBusinessError`（Task 3）。
- Produces: `HospitalToolContext` 新增两个带默认值的字段：`conversation_id: str | None = None`、`writes_enabled: bool = False`。
- Produces: `create_registration`、`cancel_registration` 两个 LangChain tool；抛出的 `interrupt()` 载荷形如
  `{"kind": "registration_create" | "registration_cancel", "prompt": str, "detail": dict}`，`detail` 的键是驼峰，供前端直接渲染。

- [ ] **Step 1: 写失败的测试**

创建 `ai-python/tests/unit/test_registration_write_tools.py`：

```python
import os

os.environ.setdefault("DASHSCOPE_CHAT_MODEL", "test-model")
os.environ.setdefault("DASHSCOPE_API_KEY", "test-key")
os.environ.setdefault(
    "DASHSCOPE_BASE_URL",
    "https://dashscope.aliyuncs.com/compatible-mode/v1",
)

from datetime import datetime

import pytest
from langchain.tools import ToolRuntime

from app.graphs.hospital.tools import registration_write as write_module
from app.graphs.hospital.tools.context import CLINIC_TZ, HospitalToolContext
from app.services.java_tool_client import (
    JavaToolBusinessError,
    JavaToolClientError,
    Registration,
    Schedule,
)

FROZEN_NOW = datetime(2026, 9, 1, 11, 15, tzinfo=CLINIC_TZ)
CONTEXT = HospitalToolContext(
    "delegated-token",
    "trace-123",
    now=FROZEN_NOW,
    conversation_id="conversation-1",
    writes_enabled=True,
)

SCHEDULE = Schedule(
    id=9,
    dept_name="内科",
    staff_name="张伟",
    work_date="2026-09-04",
    time_period="下午",
    total_count=20,
    remaining_count=3,
    register_fee="50.00",
)

REGISTRATION = Registration(
    id=55,
    reg_no="REG-2026-0001",
    dept_name="内科",
    staff_name="张伟",
    work_date="2026-09-04",
    time_period="下午",
    status=1,
    reg_fee="50.00",
)


def _runtime() -> ToolRuntime:
    return ToolRuntime(
        state={},
        context=CONTEXT,
        config={},
        stream_writer=lambda _: None,
        tool_call_id="call-1",
        store=None,
    )


class FakeClient:
    """记录调用顺序，便于断言「确认前绝不写库」。"""

    def __init__(self, *, schedule=SCHEDULE, registrations=None, create_error=None):
        self.schedule = schedule
        self.registrations = [REGISTRATION] if registrations is None else registrations
        self.create_error = create_error
        self.writes: list[dict] = []

    def get_schedule(self, token, request_id, *, schedule_id):
        return self.schedule

    def list_my_registrations(self, token, request_id):
        return self.registrations

    def create_registration(self, token, request_id, *, schedule_id, idempotency_key):
        if self.create_error is not None:
            raise self.create_error
        self.writes.append({"schedule_id": schedule_id, "idempotency_key": idempotency_key})
        return 55

    def cancel_registration(self, token, request_id, *, registration_id):
        self.writes.append({"registration_id": registration_id})


def _install(monkeypatch, client: FakeClient) -> FakeClient:
    monkeypatch.setattr(write_module, "JavaToolClient", lambda: client)
    return client


def _install_decision(monkeypatch, decision: str) -> None:
    monkeypatch.setattr(write_module, "interrupt", lambda payload: decision)


class Paused(Exception):
    """替身：真实的 interrupt() 会中止本次执行，这里用哨兵异常模拟同样的控制流。"""


def test_create_registration_interrupts_with_authoritative_schedule(monkeypatch):
    client = _install(monkeypatch, FakeClient())
    captured: dict = {}

    def fake_interrupt(payload):
        captured.update(payload)
        raise Paused()

    monkeypatch.setattr(write_module, "interrupt", fake_interrupt)

    with pytest.raises(Paused):
        write_module.create_registration.func(schedule_id=9, runtime=_runtime())

    assert captured["kind"] == "registration_create"
    assert captured["detail"]["staffName"] == "张伟"
    assert captured["detail"]["workDate"] == "2026-09-04"
    assert captured["detail"]["registerFee"] == "50.00"
    # 确认前一次都不能写库。
    assert client.writes == []


def test_create_registration_submits_with_stable_idempotency_key(monkeypatch):
    client = _install(monkeypatch, FakeClient())
    _install_decision(monkeypatch, "approve")

    reply = write_module.create_registration.func(schedule_id=9, runtime=_runtime())

    assert client.writes == [
        {"schedule_id": 9, "idempotency_key": "conversation-1:call-1"}
    ]
    assert "挂号已办好" in reply


def test_create_registration_does_not_write_when_rejected(monkeypatch):
    client = _install(monkeypatch, FakeClient())
    _install_decision(monkeypatch, "reject")

    reply = write_module.create_registration.func(schedule_id=9, runtime=_runtime())

    assert client.writes == []
    assert "没有提交" in reply


def test_create_registration_stops_before_confirming_when_slot_is_full(monkeypatch):
    client = _install(monkeypatch, FakeClient(schedule=Schedule(id=9, remaining_count=0)))

    def fail_interrupt(payload):
        raise AssertionError("号源为 0 时不应该弹确认卡片")

    monkeypatch.setattr(write_module, "interrupt", fail_interrupt)

    assert "已约满" in write_module.create_registration.func(schedule_id=9, runtime=_runtime())
    assert client.writes == []


def test_create_registration_relays_business_rejection_in_chinese(monkeypatch):
    _install(monkeypatch, FakeClient(create_error=JavaToolBusinessError("您已预约该医生此时段，不能重复挂号")))
    _install_decision(monkeypatch, "approve")

    reply = write_module.create_registration.func(schedule_id=9, runtime=_runtime())

    assert "您已预约该医生此时段，不能重复挂号" in reply


def test_create_registration_degrades_when_java_is_unavailable(monkeypatch):
    class BrokenClient(FakeClient):
        def get_schedule(self, token, request_id, *, schedule_id):
            raise JavaToolClientError("Java Tool API is unavailable")

    _install(monkeypatch, BrokenClient())

    assert (
        write_module.create_registration.func(schedule_id=9, runtime=_runtime())
        == "暂时无法查询医院业务信息，请稍后重试。"
    )


def test_cancel_registration_submits_after_approval(monkeypatch):
    client = _install(monkeypatch, FakeClient())
    _install_decision(monkeypatch, "approve")

    reply = write_module.cancel_registration.func(registration_id=55, runtime=_runtime())

    assert client.writes == [{"registration_id": 55}]
    assert "已为您退号" in reply


def test_cancel_registration_rejects_unknown_registration(monkeypatch):
    client = _install(monkeypatch, FakeClient(registrations=[]))

    reply = write_module.cancel_registration.func(registration_id=55, runtime=_runtime())

    assert "没有找到" in reply
    assert client.writes == []


def test_cancel_registration_rejects_already_finished_registration(monkeypatch):
    finished = Registration(id=55, reg_no="REG-1", status=3)
    client = _install(monkeypatch, FakeClient(registrations=[finished]))

    reply = write_module.cancel_registration.func(registration_id=55, runtime=_runtime())

    assert "不是已挂号状态" in reply
    assert client.writes == []


def test_context_defaults_keep_writes_disabled():
    default_context = HospitalToolContext("token", "trace")

    assert default_context.writes_enabled is False
    assert default_context.conversation_id is None
```

- [ ] **Step 2: 跑测试确认失败**

```powershell
cd ai-python
python -m pytest tests/unit/test_registration_write_tools.py -v
```

预期：collection 阶段报 `ModuleNotFoundError: No module named 'app.graphs.hospital.tools.registration_write'`。

- [ ] **Step 3: 给运行时上下文加两个字段**

把 `ai-python/app/graphs/hospital/tools/context.py` 末尾的

```python
@dataclass(frozen=True)
class HospitalToolContext:
    delegated_token: str
    request_id: str | None = None
    now: datetime = field(default_factory=clinic_now)
```

替换为：

```python
@dataclass(frozen=True)
class HospitalToolContext:
    delegated_token: str
    request_id: str | None = None
    now: datetime = field(default_factory=clinic_now)
    #: 幂等键的前缀来源。与 checkpointer 的 thread_id 相同。
    conversation_id: str | None = None
    #: 只有会话带 checkpointer 且不是快速模式时才为 True。为 False 时不挂载写工具，
    #: 否则 interrupt() 会静默失效：工具不执行，final_reply 为空，整轮对话变成 500。
    writes_enabled: bool = False
```

- [ ] **Step 4: 实现写工具**

创建 `ai-python/app/graphs/hospital/tools/registration_write.py`：

```python
"""挂号与退号写工具。

提交前一律先 interrupt() 等患者确认，确认卡片上的业务信息全部来自 Java，
不采用模型复述的内容——否则患者确认的和实际提交的可能不是同一张号。
"""

from typing import Any

from langchain.tools import ToolRuntime, tool
from langgraph.types import interrupt
from loguru import logger

from app.graphs.hospital.tools.base import UNAVAILABLE_MESSAGE
from app.graphs.hospital.tools.context import HospitalToolContext
from app.services.java_tool_client import (
    JavaToolBusinessError,
    JavaToolClient,
    JavaToolClientError,
)

MAX_IDEMPOTENCY_KEY_LENGTH = 128
REGISTERED_STATUS = 1


def _idempotency_key(context: HospitalToolContext, tool_call_id: str) -> str:
    """患者确认后节点会整段重跑，tool_call_id 不变，所以这个键在重放时保持稳定。"""
    return f"{context.conversation_id or 'na'}:{tool_call_id}"[:MAX_IDEMPOTENCY_KEY_LENGTH]


def _slot_text(detail: dict[str, Any]) -> str:
    parts = [
        detail.get(key)
        for key in ("workDate", "timePeriod", "deptName", "staffName")
        if detail.get(key)
    ]
    return " ".join(str(part) for part in parts)


@tool
def create_registration(schedule_id: int, runtime: ToolRuntime[HospitalToolContext]) -> str:
    """为当前登录患者提交挂号。schedule_id 必须来自 list_schedules 返回的排班，不能猜。"""
    context = runtime.context
    client = JavaToolClient()
    try:
        schedule = client.get_schedule(
            context.delegated_token, context.request_id, schedule_id=schedule_id
        )
    except JavaToolClientError:
        logger.exception(
            "create_registration_schedule_lookup_failed request_id={} schedule_id={}",
            context.request_id,
            schedule_id,
        )
        return UNAVAILABLE_MESSAGE

    if schedule.remaining_count is not None and schedule.remaining_count <= 0:
        return "这个时段的号已约满，请换一个时段。"

    detail = {
        "scheduleId": schedule.id,
        "deptName": schedule.dept_name,
        "staffName": schedule.staff_name,
        "workDate": schedule.work_date,
        "timePeriod": schedule.time_period,
        "remainingCount": schedule.remaining_count,
        "registerFee": schedule.register_fee,
    }
    decision = interrupt(
        {
            "kind": "registration_create",
            "prompt": f"请确认是否为您挂 {_slot_text(detail)} 的号",
            "detail": detail,
        }
    )
    if decision != "approve":
        return "患者取消了本次挂号，没有提交。"

    try:
        client.create_registration(
            context.delegated_token,
            context.request_id,
            schedule_id=schedule_id,
            idempotency_key=_idempotency_key(context, runtime.tool_call_id),
        )
    except JavaToolBusinessError as exc:
        return f"挂号没有成功：{exc}"
    except JavaToolClientError:
        logger.exception(
            "create_registration_failed request_id={} schedule_id={}",
            context.request_id,
            schedule_id,
        )
        return UNAVAILABLE_MESSAGE
    return f"挂号已办好：{_slot_text(detail)}。"


@tool
def cancel_registration(registration_id: int, runtime: ToolRuntime[HospitalToolContext]) -> str:
    """为当前登录患者退号。registration_id 必须来自 list_my_registrations，不能猜。"""
    context = runtime.context
    client = JavaToolClient()
    try:
        registrations = client.list_my_registrations(
            context.delegated_token, context.request_id
        )
    except JavaToolClientError:
        logger.exception(
            "cancel_registration_lookup_failed request_id={} registration_id={}",
            context.request_id,
            registration_id,
        )
        return UNAVAILABLE_MESSAGE

    target = next((item for item in registrations if item.id == registration_id), None)
    if target is None:
        return "没有找到这张挂号单，请先查一下您名下的挂号记录再确认。"
    if target.status != REGISTERED_STATUS:
        return "这张挂号单当前不是已挂号状态，不能退号。"

    detail = {
        "registrationId": target.id,
        "regNo": target.reg_no,
        "deptName": target.dept_name,
        "staffName": target.staff_name,
        "workDate": target.work_date,
        "timePeriod": target.time_period,
        "regFee": target.reg_fee,
    }
    decision = interrupt(
        {
            "kind": "registration_cancel",
            "prompt": f"请确认是否退掉 {_slot_text(detail)} 的号",
            "detail": detail,
        }
    )
    if decision != "approve":
        return "患者取消了本次退号，挂号单保持不变。"

    try:
        client.cancel_registration(
            context.delegated_token, context.request_id, registration_id=registration_id
        )
    except JavaToolBusinessError as exc:
        return f"退号没有成功：{exc}"
    except JavaToolClientError:
        logger.exception(
            "cancel_registration_failed request_id={} registration_id={}",
            context.request_id,
            registration_id,
        )
        return UNAVAILABLE_MESSAGE
    return f"已为您退号：{_slot_text(detail)}。"
```

- [ ] **Step 5: 导出写工具**

把 `ai-python/app/graphs/hospital/tools/__init__.py` 整个替换为：

```python
"""医院图使用的 LangChain Tool。HTTP 适配器在 app.services，不放在本包。"""

from app.graphs.hospital.tools.context import HospitalToolContext
from app.graphs.hospital.tools.departments import list_departments
from app.graphs.hospital.tools.knowledge_base import (
    retrieve_hospital_documents,
    search_hospital_knowledge,
)
from app.graphs.hospital.tools.registration_write import (
    cancel_registration,
    create_registration,
)
from app.graphs.hospital.tools.registrations import list_my_registrations
from app.graphs.hospital.tools.schedules import list_schedules
from app.graphs.hospital.tools.search import web_search
from app.graphs.hospital.tools.staff import list_doctors

__all__ = [
    "HospitalToolContext",
    "cancel_registration",
    "create_registration",
    "list_departments",
    "list_doctors",
    "list_my_registrations",
    "list_schedules",
    "retrieve_hospital_documents",
    "search_hospital_knowledge",
    "web_search",
]
```

- [ ] **Step 6: 把写工具纳入导出契约测试**

在 `ai-python/tests/unit/test_tools_layout.py` 里，把

```python
    assert hospital_tools.list_my_registrations.name == "list_my_registrations"
```

替换为：

```python
    assert hospital_tools.list_my_registrations.name == "list_my_registrations"
    assert hospital_tools.create_registration.name == "create_registration"
    assert hospital_tools.cancel_registration.name == "cancel_registration"
```

- [ ] **Step 7: 跑测试确认通过**

```powershell
python -m pytest tests/unit/test_registration_write_tools.py tests/unit/test_tools_layout.py -v
```

预期：全部 PASS。

- [ ] **Step 8: 提交**

```powershell
cd ..
git add ai-python/app/graphs/hospital/tools/context.py ai-python/app/graphs/hospital/tools/registration_write.py ai-python/app/graphs/hospital/tools/__init__.py ai-python/tests/unit/test_registration_write_tools.py ai-python/tests/unit/test_tools_layout.py
git commit -m "feat(ai): 新增带患者确认中断的挂号与退号写工具"
```

---

### Task 5: tool_node 按会话能力挂载可写 Agent

**背景：** 写工具不能无条件挂上去。没有 checkpointer 时（`memoryEnabled=false`，或 Redis 没连上导致 `get_memory_graph()` 返回 `None`），`interrupt()` 实测不会抛错，而是让整轮对话静默变成「工具没执行 + `final_reply` 为空」，最终被 `_response_from_state` 打成 500。快速模式没有 `final_node` 汇总，也不适合做写操作。

**设计取向：** 保留现有的只读 `agent` 与只读 `TOOL_SYSTEM_PROMPT` 一字不改，另建一个 `writable_agent` 与 `WRITE_TOOL_SYSTEM_PROMPT`，`tool_node` 按 `context.writes_enabled` 二选一。这样只读路径零风险，现有测试全部保持有效。

**Files:**
- Modify: `ai-python/app/graphs/hospital/nodes/tool.py`
- Test: `ai-python/tests/unit/test_tool_node.py`

**Interfaces:**
- Consumes: `create_registration`、`cancel_registration`（Task 4）；`HospitalToolContext.writes_enabled`（Task 4）。
- Produces: `tool_node_module.writable_agent`、`tool_node_module.HOSPITAL_WRITE_TOOLS`、`tool_node_module.WRITE_TOOL_SYSTEM_PROMPT`。
- Produces: `tool_node(state, runtime)` 在 `runtime.context.writes_enabled` 为 True 时调用 `writable_agent`，否则调用 `agent`；返回值形状不变，仍是 `{"tools_reply": str}`。

- [ ] **Step 1: 写失败的测试**

在 `tests/unit/test_tool_node.py` 末尾追加：

```python
def test_write_tools_are_only_mounted_on_the_writable_agent():
    read_only = {item.name for item in tool_node_module.HOSPITAL_TOOLS}
    writable = {item.name for item in tool_node_module.HOSPITAL_WRITE_TOOLS}

    assert writable == {"create_registration", "cancel_registration"}
    assert not (read_only & writable)


def test_write_prompt_documents_every_write_tool_and_forbids_faking_success():
    prompt = tool_node_module.WRITE_TOOL_SYSTEM_PROMPT

    for name in ("create_registration", "cancel_registration"):
        assert name in prompt
    # 确认卡片由系统渲染，模型不能自己声称已经办好。
    assert "不要在患者确认之前说已经挂上" in prompt


def test_tool_node_uses_read_only_agent_when_writes_are_disabled(monkeypatch):
    used: list[str] = []

    class FakeAgent:
        def __init__(self, label):
            self.label = label

        def invoke(self, payload, *, context):
            used.append(self.label)
            return {"messages": [HumanMessage(content="好的。")]}

    monkeypatch.setattr(tool_node_module, "agent", FakeAgent("read"))
    monkeypatch.setattr(tool_node_module, "writable_agent", FakeAgent("write"))

    tool_node_module.tool_node(
        {"selected_agents": ["tools"], "messages": [HumanMessage(content="帮我挂号")]},
        _graph_runtime(CONTEXT),
    )

    assert used == ["read"]


def test_tool_node_uses_writable_agent_when_writes_are_enabled(monkeypatch):
    used: list[str] = []

    class FakeAgent:
        def __init__(self, label):
            self.label = label

        def invoke(self, payload, *, context):
            used.append(self.label)
            return {"messages": [HumanMessage(content="好的。")]}

    monkeypatch.setattr(tool_node_module, "agent", FakeAgent("read"))
    monkeypatch.setattr(tool_node_module, "writable_agent", FakeAgent("write"))
    writable_context = HospitalToolContext(
        "delegated-token",
        "trace-123",
        now=FROZEN_NOW,
        conversation_id="conversation-1",
        writes_enabled=True,
    )

    tool_node_module.tool_node(
        {"selected_agents": ["tools"], "messages": [HumanMessage(content="帮我挂号")]},
        _graph_runtime(writable_context),
    )

    assert used == ["write"]
```

- [ ] **Step 2: 跑测试确认失败**

```powershell
cd ai-python
python -m pytest tests/unit/test_tool_node.py -v
```

预期：4 个新测试 FAIL，报 `AttributeError: module ... has no attribute 'HOSPITAL_WRITE_TOOLS'`。

- [ ] **Step 3: 加可写 prompt**

在 `ai-python/app/graphs/hospital/nodes/tool.py` 里，`TOOL_SYSTEM_PROMPT` 常量定义之后、`build_tool_system_prompt` 之前插入：

```python
WRITE_TOOL_SYSTEM_PROMPT = """你是温润诊所的患者端业务助手。用简短、尊重、有温度的中文直接回复患者。

工作流程（必须按顺序，不要跳步）：
1. 需要本院实时业务数据时，先调用工具，再根据工具返回的内容回答。
2. 按问题选择工具：
   - 有哪些科室、开了哪些科、能看哪些科 → list_departments
   - 某科有哪些医生、有没有某位医生 → list_doctors
   - 某科或某位医生的排班、某天有没有号、余号多少 → list_schedules
   - 我挂了什么号、我的预约、我的号退了没 → list_my_registrations
3. 一个问题需要多项数据时，可以连续调用多个工具，全部拿到后再统一回答。
4. 只根据工具结果陈述事实，不补充自己的假设，不把工具没返回的日期说成「今天/明天」。
5. 患者要挂号时：先用 list_schedules 查到确切的排班，拿到它的 id，再调用 create_registration 并把这个 id 传进去。
   排班 id 必须来自工具返回，绝对不能猜、不能凭印象填。
   患者的说法对应多个可选号源时，先把可选项列出来问清楚要哪一个，再提交。
6. 患者要退号时：先用 list_my_registrations 查到那张挂号单，拿到它的 id，再调用 cancel_registration。
   患者名下有多张有效挂号单时，先列出来问清楚退哪一张，再提交。
7. create_registration 和 cancel_registration 会先把一张确认卡片交给患者，由患者本人点确认。
   卡片由系统渲染，你不需要复述卡片内容，也不要在患者确认之前说已经挂上或已经退掉。
   工具返回结果后，如实转达成功或失败的原因。
8. 工具返回「暂时无法查询」或提示姓名、科室不对时，如实转达并请患者确认或稍后重试，不要编造数据。

工具参数：
- 科室、医生用患者的说法即可，例如 department="内科"、doctor="张伟"。
- 日期：系统提示里有当前北京时间。调用 list_schedules 时可把「今天 / 明天 / 这周五」换成 YYYY-MM-DD，也可以直接传「今天」「明天」。
- 问今天几号、星期几：直接根据系统给出的当前时间回答，不必调用工具。
- list_my_registrations 只会返回当前登录患者本人的记录，你无法也不要尝试查询他人。

你不要做：
- 不改排班、不调号源总量、不替他人挂号或退号
- 不解释症状、用药、是否需要就医，也不说某科通常看什么病
- 不闲聊、不陪聊
- 不编造科室名、医生、号源、时间、费用或链接
- 余号为 0 时如实说明已约满，不要暗示还能加号

多意图时：患者一句话里若同时有业务查询和医疗提问/寒暄，你只回答业务查询部分，其余留给其他助手。
"""
```

- [ ] **Step 4: 挂载可写 Agent 并按上下文分流**

把 `tool.py` 里 `build_tool_system_prompt` 与 `hospital_tool_prompt` 之间的部分扩成两套。具体地，把

```python
def build_tool_system_prompt(now: datetime) -> str:
    """静态职责说明 + 本次请求的北京时间。"""
    return TOOL_SYSTEM_PROMPT + f"\n\n当前时间：{format_clinic_clock(now)}。"


@dynamic_prompt
def hospital_tool_prompt(request: ModelRequest) -> str:
    return build_tool_system_prompt(request.runtime.context.now)
```

替换为：

```python
def build_tool_system_prompt(now: datetime) -> str:
    """静态职责说明 + 本次请求的北京时间。"""
    return TOOL_SYSTEM_PROMPT + f"\n\n当前时间：{format_clinic_clock(now)}。"


def build_write_tool_system_prompt(now: datetime) -> str:
    """可写会话的职责说明 + 本次请求的北京时间。"""
    return WRITE_TOOL_SYSTEM_PROMPT + f"\n\n当前时间：{format_clinic_clock(now)}。"


@dynamic_prompt
def hospital_tool_prompt(request: ModelRequest) -> str:
    return build_tool_system_prompt(request.runtime.context.now)


@dynamic_prompt
def hospital_write_tool_prompt(request: ModelRequest) -> str:
    return build_write_tool_system_prompt(request.runtime.context.now)
```

把 import 区的

```python
from app.graphs.hospital.tools import (
    HospitalToolContext,
    list_departments,
    list_doctors,
    list_my_registrations,
    list_schedules,
)
```

替换为：

```python
from app.graphs.hospital.tools import (
    HospitalToolContext,
    cancel_registration,
    create_registration,
    list_departments,
    list_doctors,
    list_my_registrations,
    list_schedules,
)
```

把

```python
HOSPITAL_TOOLS = [
    list_departments,
    list_doctors,
    list_schedules,
    list_my_registrations,
]

agent = create_agent(
    model=model,
    tools=HOSPITAL_TOOLS,
    context_schema=HospitalToolContext,
    middleware=[hospital_tool_prompt],
)
```

替换为：

```python
HOSPITAL_TOOLS = [
    list_departments,
    list_doctors,
    list_schedules,
    list_my_registrations,
]

HOSPITAL_WRITE_TOOLS = [
    create_registration,
    cancel_registration,
]

agent = create_agent(
    model=model,
    tools=HOSPITAL_TOOLS,
    context_schema=HospitalToolContext,
    middleware=[hospital_tool_prompt],
)

# 写工具靠 interrupt() 暂停等患者确认，而 interrupt 需要 checkpointer 才能恢复。
# 没有 checkpointer 时它不会报错，只会静默地什么都不做，所以这个 Agent 只在
# runtime context 明确开启写能力时才使用。
writable_agent = create_agent(
    model=model,
    tools=HOSPITAL_TOOLS + HOSPITAL_WRITE_TOOLS,
    context_schema=HospitalToolContext,
    middleware=[hospital_write_tool_prompt],
)
```

把 `tool_node` 里的

```python
    ##任务三：运行时上下文只在本次请求内有效，直接透传给嵌套 Agent
    result = agent.invoke(
        {"messages": recent_messages(state)},
        context=context,
    )
```

替换为：

```python
    ##任务三：运行时上下文只在本次请求内有效，直接透传给嵌套 Agent
    selected = writable_agent if getattr(context, "writes_enabled", False) else agent
    result = selected.invoke(
        {"messages": recent_messages(state)},
        context=context,
    )
```

- [ ] **Step 5: 跑 Python 单元测试确认通过**

```powershell
python -m pytest tests/unit -v
```

预期：全部 PASS。`test_every_hospital_tool_is_mounted_and_documented` 仍然只断言 `HOSPITAL_TOOLS` 里的四个只读工具，不受影响。

- [ ] **Step 6: 提交**

```powershell
cd ..
git add ai-python/app/graphs/hospital/nodes/tool.py ai-python/tests/unit/test_tool_node.py
git commit -m "feat(ai): 会话具备恢复能力时才挂载可写业务 Agent"
```

---

### Task 6: SSE 发出 confirm 事件并新增 resume 端点

**背景：** 中断发生时，`astream` 会正常结束，但根图的 `final_reply` 是空的，现在的代码会走进 `_response_from_state` 并抛 500。实测确认：中断信息不在 `part["data"]` 里，而是挂在 values 分片的 `interrupts` 键上；最可靠的读法是流结束后 `await graph.aget_state(config)` 读 `snapshot.interrupts`。

本任务把事件生成逻辑抽成一个可复用的异步生成器，让 `/stream` 和 `/resume` 共用，并在流末尾判断有没有待确认的中断。

**Files:**
- Modify: `ai-python/app/models/chat.py`
- Modify: `ai-python/app/api/routes/chat.py`
- Modify: `docs/AI模块开发与运维指南.md`
- Test: `ai-python/tests/test_app.py`

**Interfaces:**
- Consumes: `HospitalToolContext(conversation_id=..., writes_enabled=...)`（Task 4）。
- Produces: `ChatResumeRequest`，字段 `conversation_id: str`（别名 `conversationId`）、`decision: Literal["approve", "reject"]`、`user_context: UserContext`（别名 `userContext`）。
- Produces: SSE 新事件 `{"type": "confirm", "conversationId": str, "kind": str, "prompt": str, "detail": dict}`。发出后本次流即结束，**不再发 `done`**。
- Produces: `POST /v1/chat/resume`，同样是 `text/event-stream`，事件协议与 `/stream` 完全一致。

- [ ] **Step 1: 写失败的测试**

`tests/test_app.py` 里已有 `_sse_events(response)` 与 `_chat_auth_headers(monkeypatch)` 两个辅助函数，且现有 SSE 测试统一用 `monkeypatch.setattr(chat_route, "graph", FakeGraph())` 替换模块级图对象——沿用这一套，不要另起炉灶。

在 `tests/test_app.py` 顶部的 import 区追加：

```python
from types import SimpleNamespace
```

在文件末尾追加：

```python
def test_chat_stream_emits_confirm_event_when_graph_pauses_for_approval(monkeypatch):
    """写工具挂起时必须发 confirm，而不是把空 final_reply 打成 500。"""

    headers = _chat_auth_headers(monkeypatch)

    class PausedGraph:
        # 有 checkpointer 才会开启写能力，也才能读到挂起的确认请求。
        checkpointer = object()

        async def astream(self, state, *, context, config, stream_mode, subgraphs, version):
            assert context.writes_enabled is True
            assert context.conversation_id == "conversation-1"
            yield {"type": "values", "data": {"selected_agents": ["tools"]}}

        async def aget_state(self, config):
            return SimpleNamespace(interrupts=(
                SimpleNamespace(value={
                    "kind": "registration_create",
                    "prompt": "请确认是否为您挂 2026-09-04 下午 内科 张伟 的号",
                    "detail": {"scheduleId": 9, "staffName": "张伟"},
                }),
            ))

    monkeypatch.setattr(chat_route, "graph", PausedGraph())
    client = TestClient(create_app())
    response = client.post(
        "/v1/chat/stream",
        headers=headers,
        json={"message": "帮我挂明天下午张伟的号", "conversationId": "conversation-1"},
    )

    assert response.status_code == 200
    events = _sse_events(response)
    types = [event["type"] for event in events]
    assert "confirm" in types
    assert "done" not in types
    confirm = next(event for event in events if event["type"] == "confirm")
    assert confirm["kind"] == "registration_create"
    assert confirm["detail"]["scheduleId"] == 9
    assert confirm["conversationId"] == "conversation-1"


def test_chat_stream_keeps_writes_disabled_without_a_checkpointer(monkeypatch):
    """无记忆会话恢复不了中断，必须关掉写能力，否则整轮会静默失败。"""

    headers = _chat_auth_headers(monkeypatch)

    class StatelessGraph:
        async def astream(self, state, *, context, config, stream_mode, subgraphs, version):
            assert context.writes_enabled is False
            yield {"type": "values", "data": {"final_reply": "已生成回复", "selected_agents": ["tools"]}}

    monkeypatch.setattr(chat_route, "graph", StatelessGraph())
    client = TestClient(create_app())
    response = client.post(
        "/v1/chat/stream",
        headers=headers,
        json={"message": "帮我挂号", "conversationId": "conversation-2", "memoryEnabled": False},
    )

    assert [event["type"] for event in _sse_events(response)][-1] == "done"


def test_chat_resume_forwards_decision_into_the_graph(monkeypatch):
    headers = _chat_auth_headers(monkeypatch)
    captured: dict = {}

    class ResumedGraph:
        checkpointer = object()

        async def astream(self, state, *, context, config, stream_mode, subgraphs, version):
            captured["input"] = state
            captured["thread_id"] = config["configurable"]["thread_id"]
            yield {
                "type": "values",
                "data": {"final_reply": "挂号已办好。", "selected_agents": ["tools"]},
            }

        async def aget_state(self, config):
            return SimpleNamespace(interrupts=())

    monkeypatch.setattr(chat_route, "graph", ResumedGraph())
    client = TestClient(create_app())
    response = client.post(
        "/v1/chat/resume",
        headers=headers,
        json={"conversationId": "conversation-1", "decision": "approve"},
    )

    assert response.status_code == 200
    events = _sse_events(response)
    assert events[-1]["type"] == "done"
    assert events[-1]["reply"] == "挂号已办好。"
    assert captured["thread_id"] == "conversation-1"
    assert captured["input"].resume == "approve"


def test_chat_resume_rejects_unknown_decision(monkeypatch):
    headers = _chat_auth_headers(monkeypatch)
    client = TestClient(create_app())

    response = client.post(
        "/v1/chat/resume",
        headers=headers,
        json={"conversationId": "conversation-1", "decision": "maybe"},
    )

    assert response.status_code == 422
```

- [ ] **Step 2: 跑测试确认失败**

```powershell
cd ai-python
python -m pytest tests/test_app.py -v
```

预期：4 个新测试里有 3 个 FAIL。

- `test_chat_stream_emits_confirm_event_when_graph_pauses_for_approval`：现在 `context` 上没有 `writes_enabled` 断言想要的 True，且流末尾直接走 `_response_from_state`，只会收到一条 `error` 事件。
- `test_chat_resume_forwards_decision_into_the_graph` 与 `test_chat_resume_rejects_unknown_decision`：`/v1/chat/resume` 还不存在，返回 404。
- `test_chat_stream_keeps_writes_disabled_without_a_checkpointer` 这条现在就会 PASS（`writes_enabled` 的默认值本来就是 False），它是防回归用的，确保后面加上 `_writes_enabled` 之后无记忆会话不会被误开写能力。

- [ ] **Step 3: 加恢复请求模型**

在 `ai-python/app/models/chat.py` 的 `ChatRequest` 之后插入：

```python
class ChatResumeRequest(ApiModel):
    """患者对确认卡片作出选择后，恢复被挂起的那一轮对话。"""

    conversation_id: str = Field(alias="conversationId", min_length=1, max_length=64)
    decision: Literal["approve", "reject"]
    user_context: UserContext = Field(default_factory=UserContext, alias="userContext")
```

`Literal` 已经在该文件顶部被导入（`ChatResponse.status` 用到了），不需要新增 import。

- [ ] **Step 4: 重构 chat.py 的事件生成**

在 `chat.py` 的 import 区，把

```python
from app.models.chat import ChatRequest, ChatResponse
```

替换为：

```python
from app.models.chat import ChatRequest, ChatResponse, ChatResumeRequest
```

并追加：

```python
from langgraph.types import Command
```

把 `_response_from_state`、`_runtime_context`、`_graph_config`、`_stream_graph` 四个函数替换为下面这一组：

```python
def _response_from_state(conversation_id: str, result: dict[str, Any]) -> ChatResponse:
    reply = result.get("final_reply")
    if not isinstance(reply, str) or not reply.strip():
        logger.error("chat_graph_missing_final_reply conversation_id={}", conversation_id)
        raise HTTPException(status_code=500, detail="AI 对话未生成有效回复")

    selected_agents: list[str] = []
    for agent_name in result.get("selected_agents") or []:
        if isinstance(agent_name, str):
            selected_agents.append(agent_name)

    sources: list[dict[str, Any]] = []
    for source in result.get("rag_sources") or []:
        if isinstance(source, dict):
            sources.append(source)

    return ChatResponse(
        reply=reply.strip(),
        conversation_id=conversation_id,
        selected_agents=selected_agents,
        sources=sources,
    )


def _runtime_context(
    conversation_id: str,
    delegation: DelegationContext,
    *,
    writes_enabled: bool,
) -> HospitalToolContext:
    """委托令牌与追踪号只在本次请求内有效，绝不进入持久化 State。"""

    return HospitalToolContext(
        delegation.token,
        current_request_id(),
        conversation_id=conversation_id,
        writes_enabled=writes_enabled,
    )


def _graph_config(conversation_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": conversation_id}}


def _writes_enabled(graph_instance: Any, fast_mode: bool) -> bool:
    """写工具靠 interrupt 暂停等确认，没有 checkpointer 就无法恢复，只能关掉。"""

    if fast_mode:
        return False
    return getattr(graph_instance, "checkpointer", None) is not None


async def _pending_confirmation(
    graph_instance: Any, config: dict[str, Any]
) -> dict[str, Any] | None:
    """读出本轮被挂起的确认请求。中断不在 astream 的 data 里，只能从状态快照拿。"""

    if getattr(graph_instance, "checkpointer", None) is None:
        return None
    snapshot = await graph_instance.aget_state(config)
    for pending in getattr(snapshot, "interrupts", ()) or ():
        value = getattr(pending, "value", None)
        if isinstance(value, dict) and value.get("kind"):
            return value
    return None


async def _stream_graph(
    graph_instance: Any,
    graph_input: Any,
    context: HospitalToolContext,
    config: dict[str, Any],
) -> AsyncIterator[dict[str, Any]]:
    """生成 LangGraph v2 流式片段。"""

    async for part in graph_instance.astream(
        graph_input,
        context=context,
        config=config,
        stream_mode=["messages", "values"],
        subgraphs=True,
        version="v2",
    ):
        if isinstance(part, dict):
            yield part
```

- [ ] **Step 5: 抽出共用的事件生成器**

把 `chat.py` 里整个 `chat_stream` 路由函数（从 `@router.post("/stream")` 到文件末尾）替换为：

```python
async def _chat_events(
    *,
    graph_instance: Any,
    graph_input: Any,
    context: HospitalToolContext,
    config: dict[str, Any],
    conversation_id: str,
    fast_mode: bool,
) -> AsyncIterator[str]:
    """/stream 与 /resume 共用的 SSE 事件流。"""

    started_at = perf_counter()
    first_token_at: float | None = None
    yield _sse({"type": "status", "content": "正在分析您的问题…"})
    graph_state: dict[str, Any] = {}
    streamed_reply = False
    selected_agents: list[str] = []
    retrieval_status_sent = False
    final_status_sent = False
    try:
        async for part in _stream_graph(graph_instance, graph_input, context, config):
            _merge_stream_state(graph_state, part)
            incoming_agents = graph_state.get("selected_agents") or []
            selected_agents = [
                agent for agent in incoming_agents if isinstance(agent, str)
            ]

            if not fast_mode and "knowledge" in selected_agents and not retrieval_status_sent:
                retrieval_status_sent = True
                yield _sse({"type": "status", "content": "正在检索相关资料…"})

            if part.get("type") != "messages":
                continue
            if part.get("ns"):
                # 嵌套 Agent（网页检索、业务工具）的模型分片属于实现细节，
                # 只转发根图节点自己产生的消息。
                continue
            data = part.get("data")
            if not isinstance(data, (list, tuple)) or len(data) != 2:
                continue
            message_chunk, metadata = data
            if not isinstance(metadata, dict):
                continue
            node_name = metadata.get("langgraph_node")
            visible_nodes = _stream_visible_nodes(selected_agents, fast_mode)
            if node_name not in visible_nodes or not _is_streamable_message(message_chunk):
                continue
            content = _text_from_message_chunk(message_chunk)
            if not fast_mode and "knowledge" in selected_agents and not final_status_sent:
                final_status_sent = True
                yield _sse({"type": "status", "content": "正在整理答案…"})
            if first_token_at is None:
                first_token_at = perf_counter()
                logger.info(
                    "chat_stream_first_token conversation_id={} elapsed_ms={}",
                    conversation_id,
                    round((first_token_at - started_at) * 1000),
                )
            streamed_reply = True
            yield _sse({"type": "token", "content": content})

        # 写工具挂起时根图不会产出 final_reply，必须在取回复之前先判断有没有待确认项。
        confirmation = await _pending_confirmation(graph_instance, config)
        if confirmation is not None:
            logger.info(
                "chat_stream_awaiting_confirmation conversation_id={} kind={}",
                conversation_id,
                confirmation.get("kind"),
            )
            yield _sse({
                "type": "confirm",
                "conversationId": conversation_id,
                "kind": confirmation.get("kind"),
                "prompt": confirmation.get("prompt"),
                "detail": confirmation.get("detail") or {},
            })
            return

        response = _response_from_state(conversation_id, graph_state)
    except HTTPException as exc:
        yield _sse({
            "type": "error",
            "code": "AI_CHAT_FAILED",
            "message": str(exc.detail),
        })
        return
    except asyncio.CancelledError:
        logger.info("chat_stream_cancelled conversation_id={}", conversation_id)
        raise
    except Exception:
        logger.exception("chat_stream_failed conversation_id={}", conversation_id)
        yield _sse({
            "type": "error",
            "code": "AI_CHAT_FAILED",
            "message": "AI 对话处理失败，请稍后再试",
        })
        return

    for source in response.sources:
        yield _sse({"type": "citation", "sources": [source]})
    if not streamed_reply:
        # 如果服务提供方不提供令牌片段，则发送一个完整令牌以保持协议一致，
        # 避免返回空答案。
        yield _sse({"type": "token", "content": response.reply})
    yield _sse({
        "type": "done",
        **response.model_dump(by_alias=True),
    })
    logger.info(
        "chat_stream_completed conversation_id={} elapsed_ms={} first_token_ms={}",
        conversation_id,
        round((perf_counter() - started_at) * 1000),
        round((first_token_at - started_at) * 1000) if first_token_at is not None else None,
    )


def _event_stream(events: AsyncIterator[str]) -> StreamingResponse:
    return StreamingResponse(
        events,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/stream")
async def chat_stream(
    request: ChatRequest,
    delegation: DelegationContext = Depends(verify_delegation_token),
) -> StreamingResponse:
    """运行对话图，并通过 SSE 暴露增量模型输出。"""

    graph_instance = _graph_for(request.memory_enabled, request.fast_mode)
    writes_enabled = _writes_enabled(graph_instance, request.fast_mode)
    return _event_stream(_chat_events(
        graph_instance=graph_instance,
        graph_input=_initial_state(request),
        context=_runtime_context(
            request.conversation_id, delegation, writes_enabled=writes_enabled
        ),
        config=_graph_config(request.conversation_id),
        conversation_id=request.conversation_id,
        fast_mode=request.fast_mode,
    ))


@router.post("/resume")
async def chat_resume(
    request: ChatResumeRequest,
    delegation: DelegationContext = Depends(verify_delegation_token),
) -> StreamingResponse:
    """患者在确认卡片上作出选择后，续跑同一个 thread 上被挂起的那一轮。"""

    # 恢复必须落在带 checkpointer 的正常图上：快速模式没有写工具，无记忆图无从恢复。
    graph_instance = _graph_for(memory_enabled=True, fast_mode=False)
    if getattr(graph_instance, "checkpointer", None) is None:
        raise HTTPException(status_code=409, detail="会话已过期，请重新发起办理")

    return _event_stream(_chat_events(
        graph_instance=graph_instance,
        graph_input=Command(resume=request.decision),
        context=_runtime_context(
            request.conversation_id, delegation, writes_enabled=True
        ),
        config=_graph_config(request.conversation_id),
        conversation_id=request.conversation_id,
        fast_mode=False,
    ))
```

- [ ] **Step 6: 跑 Python 全量测试**

```powershell
python -m pytest -v
```

预期：全部 PASS。特别关注 `tests/test_app.py` 里原有的 SSE 契约测试——事件顺序与字段没有变化，只是多了一条新的终止路径。

- [ ] **Step 7: 补文档**

在 `docs/AI模块开发与运维指南.md` 的 SSE 事件类型表格里，`citation` 与 `done` 之间插入一行：

```markdown
| `confirm` | 写操作等待患者确认，本次流到此结束，不再发 `done`。字段：`conversationId`、`kind`（`registration_create` / `registration_cancel`）、`prompt`、`detail` | 前端渲染确认卡片，患者选择后调 `POST /api/ai/chat/resume` |
```

同一份文档的接口清单里补上 `POST /v1/chat/resume`（Python）与 `POST /api/ai/chat/resume`（Java）两行，说明请求体为 `{"conversationId": "...", "decision": "approve" | "reject", "clientRequestId": "..."}`。

- [ ] **Step 8: 提交**

```powershell
cd ..
git add ai-python/app/models/chat.py ai-python/app/api/routes/chat.py ai-python/tests/test_app.py docs/AI模块开发与运维指南.md
git commit -m "feat(ai): SSE 增加 confirm 暂停事件与 /v1/chat/resume 恢复端点"
```

---

### Task 7: Java 透传 confirm 并代理 resume

**背景：** `aiService` 对未知事件类型是原样透传的，不需要改。但 `aiController.stream()` 只把 `done` 和 `error` 当终态，Python 发完 `confirm` 就关流的话，会走进 `terminal.compareAndSet(false, true)` 分支，给用户额外推一条 `AI_STREAM_INCOMPLETE` 错误。

另外 `confirm` 这一轮不能落库真正的 assistant 回复（还没生成），但也不能什么都不落——否则这条 `clientRequestId` 永远停在「有 user 无 assistant」的状态，浏览器重试同一轮会一直拿到「该消息正在处理中」。落确认提示语最合适：既让历史连贯，又让幂等记录闭环。

**Files:**
- Create: `backend-java/src/main/java/com/wenrun/ai/vo/aiResumeRequest.java`
- Modify: `backend-java/src/main/java/com/wenrun/ai/service/aiService.java`
- Modify: `backend-java/src/main/java/com/wenrun/ai/controller/aiController.java`
- Test: `backend-java/src/test/java/com/wenrun/ai/service/AiServiceTest.java`

**Interfaces:**
- Consumes: Python 的 `POST /v1/chat/resume` 与 `confirm` 事件（Task 6）。
- Produces: `aiResumeRequest`，字段 `conversationId`、`decision`、`clientRequestId`，以及 `@JsonIgnore` 的 `userId`、`patientId`、`requestId`、`DelegatedToken`。
- Produces: `aiService.streamResume(aiResumeRequest request, Consumer<Map<String, Object>> consumer)`。
- Produces: `POST /api/ai/chat/resume`，返回 `SseEmitter`，事件与 `/api/ai/chat/stream` 一致。

- [ ] **Step 1: 写失败的测试**

在 `AiServiceTest.java` 末尾追加：

```java
    @Test
    void forwardsResumeDecisionToPython() {
        RestClient.Builder builder = RestClient.builder().baseUrl("http://python.test");
        MockRestServiceServer server = MockRestServiceServer.bindTo(builder).build();
        aiService service = new aiService(builder.build(), "service-key");
        server.expect(requestTo("http://python.test/v1/chat/resume"))
                .andExpect(method(HttpMethod.POST))
                .andExpect(header("X-Api-Key", "service-key"))
                .andExpect(header("X-Delegated-Token", "delegated-token"))
                .andExpect(jsonPath("$.conversationId").value("conversation-1"))
                .andExpect(jsonPath("$.decision").value("approve"))
                .andExpect(jsonPath("$.userContext.patientId").value(12))
                .andRespond(withSuccess("""
                        data: {"type":"done","reply":"挂号已办好。","conversationId":"conversation-1"}

                        """, MediaType.TEXT_EVENT_STREAM));

        aiResumeRequest request = new aiResumeRequest();
        request.setConversationId("conversation-1");
        request.setDecision("approve");
        request.setUserId(7L);
        request.setPatientId(12L);
        request.setDelegatedToken("delegated-token");
        List<Map<String, Object>> events = new ArrayList<>();

        service.streamResume(request, events::add);

        assertEquals(List.of("done"), events.stream().map(event -> event.get("type")).toList());
        server.verify();
    }

    @Test
    void resumeRejectsBlankDecision() {
        RestClient.Builder builder = RestClient.builder().baseUrl("http://python.test");
        aiService service = new aiService(builder.build(), "");

        aiResumeRequest request = new aiResumeRequest();
        request.setConversationId("conversation-1");

        BusinessException exception = assertThrows(
                BusinessException.class,
                () -> service.streamResume(request, event -> { }));

        assertEquals(ResultCode.BAD_REQUEST, exception.getCode());
    }
```

在该测试文件的 import 区追加：

```java
import com.wenrun.ai.vo.aiResumeRequest;
```

- [ ] **Step 2: 跑测试确认失败**

```powershell
mvn -o test "-Dtest=AiServiceTest"
```

预期：编译失败，`cannot find symbol: class aiResumeRequest`。

- [ ] **Step 3: 新建恢复请求 VO**

创建 `backend-java/src/main/java/com/wenrun/ai/vo/aiResumeRequest.java`：

```java
package com.wenrun.ai.vo;

import com.fasterxml.jackson.annotation.JsonIgnore;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;
import lombok.Data;

/** 患者在确认卡片上作出选择后，恢复被挂起的那一轮对话。 */
@Data
public class aiResumeRequest {

    @NotBlank(message = "会话 ID 不能为空")
    @Size(max = 64, message = "会话 ID 长度不能超过 64 个字符")
    private String conversationId;

    @NotBlank(message = "确认结果不能为空")
    @Pattern(regexp = "approve|reject", message = "确认结果只能是 approve 或 reject")
    private String decision;

    /** 恢复也是独立的一轮，需要自己的幂等键，不能复用被挂起那一轮的。 */
    @Size(max = 64, message = "请求 ID 长度不能超过 64 个字符")
    private String clientRequestId;

    /** 由 Java 鉴权上下文写入，不接受浏览器请求体覆盖。 */
    @JsonIgnore
    private Long userId;

    @JsonIgnore
    private Long patientId;

    @JsonIgnore
    private String requestId;

    @JsonIgnore
    private String DelegatedToken;
}
```

- [ ] **Step 4: aiService 增加 streamResume**

在 `aiService.java` 的 import 区追加：

```java
import com.wenrun.ai.vo.aiResumeRequest;
```

在 `streamChat` 方法之后插入：

```java
    /** 恢复被挂起的那一轮。委托令牌是本次请求重新签发的，Python 侧节点重跑时会读到它。 */
    public void streamResume(aiResumeRequest request, Consumer<Map<String, Object>> consumer) {
        postStream("/v1/chat/resume", buildResumePayload(request), request.getRequestId(),
                request.getDelegatedToken(), consumer);
    }
```

在 `buildChatPayload` 方法之后插入：

```java
    private Map<String, Object> buildResumePayload(aiResumeRequest request) {
        if (request == null || !StringUtils.hasText(request.getConversationId())) {
            throw new BusinessException(ResultCode.BAD_REQUEST, "会话 ID 不能为空");
        }
        String decision = request.getDecision();
        if (!"approve".equals(decision) && !"reject".equals(decision)) {
            throw new BusinessException(ResultCode.BAD_REQUEST, "确认结果只能是 approve 或 reject");
        }

        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("conversationId", request.getConversationId().trim());
        payload.put("decision", decision);
        addUserContext(payload, request.getUserId(), request.getPatientId());
        return payload;
    }
```

- [ ] **Step 5: 跑 aiService 测试确认通过**

```powershell
mvn -o test "-Dtest=AiServiceTest"
```

预期：`BUILD SUCCESS`。

- [ ] **Step 6: aiController 处理 confirm 终态并暴露 resume**

在 `aiController.java` 的 import 区追加：

```java
import com.wenrun.ai.vo.aiResumeRequest;
```

把 `stream()` 方法里的

```java
                    if ("done".equals(type)) {
                        String reply = event.get("reply") instanceof String value && StringUtils.hasText(value)
                                ? value
                                : accumulatedReply.toString();
                        saveMessage(conversationId, userId, clientRequestId, "assistant", reply);
                        terminal.set(true);
                        emitter.complete();
                    } else if ("error".equals(type)) {
                        terminal.set(true);
                        emitter.complete();
                    }
```

替换为：

```java
                    if ("done".equals(type)) {
                        String reply = event.get("reply") instanceof String value && StringUtils.hasText(value)
                                ? value
                                : accumulatedReply.toString();
                        saveMessage(conversationId, userId, clientRequestId, "assistant", reply);
                        terminal.set(true);
                        emitter.complete();
                    } else if ("confirm".equals(type)) {
                        // 写操作挂起等患者确认，本轮到此为止：Python 不会再发 done。
                        // 落一条确认提示语，让历史连贯，也让这条 clientRequestId 的幂等记录闭环。
                        String prompt = event.get("prompt") instanceof String value && StringUtils.hasText(value)
                                ? value
                                : "请确认是否继续办理";
                        saveMessage(conversationId, userId, clientRequestId, "assistant", prompt);
                        terminal.set(true);
                        emitter.complete();
                    } else if ("error".equals(type)) {
                        terminal.set(true);
                        emitter.complete();
                    }
```

在 `chatStream` 方法之后、`deleteConversation` 之前插入：

```java
    @PostMapping(value = "/chat/resume", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public SseEmitter chatResume(@Valid @RequestBody aiResumeRequest request) {
        prepareResume(request);
        return stream(
                consumer -> aiService.streamResume(request, consumer),
                request.getConversationId(),
                request.getUserId(),
                request.getClientRequestId());
    }
```

在 `prepare` 方法之后插入：

```java
    /**
     * 恢复只能发生在已存在且属于当前用户的会话上，所以用 assertOwned 而不是 establishIfAbsent。
     * 委托令牌必须重新签发：原令牌 5 分钟就过期，而患者盯着确认卡片可能想很久。
     */
    private void prepareResume(aiResumeRequest request) {
        request.setConversationId(request.getConversationId().trim());
        if (!StringUtils.hasText(request.getClientRequestId())) {
            request.setClientRequestId("client-" + UUID.randomUUID());
        } else {
            request.setClientRequestId(request.getClientRequestId().trim());
        }
        Long userId = UserContext.getUserId();
        ownershipService.assertOwned(request.getConversationId(), userId);
        request.setUserId(userId);
        request.setPatientId(currentPatientId(userId));
        request.setRequestId(RequestTrace.get());
        request.setDelegatedToken(
                delegationTokenService.issue(
                        userId,
                        UserContext.getAccountType(),
                        request.getPatientId(),
                        DelegationTokenService.PATIENT_ASSISTANT_SCOPES));
    }
```

- [ ] **Step 7: 跑整个 Java 测试套件**

```powershell
mvn -o test
```

预期：`BUILD SUCCESS`。

- [ ] **Step 8: 提交**

```powershell
git add backend-java/src/main/java/com/wenrun/ai/vo/aiResumeRequest.java backend-java/src/main/java/com/wenrun/ai/service/aiService.java backend-java/src/main/java/com/wenrun/ai/controller/aiController.java backend-java/src/test/java/com/wenrun/ai/service/AiServiceTest.java
git commit -m "feat(ai): Java 侧透传 confirm 暂停事件并代理挂号确认的恢复请求"
```

---

### Task 8: 前端确认卡片与恢复流

**背景：** `applyChatEvent` 对未知事件类型是静默忽略并继续读流的，所以不加分支的话，患者说「帮我挂号」之后界面上什么都不会发生，流读到底后还会抛「流式响应意外结束」。

**Files:**
- Modify: `frontend/src/api/modules/ai.js`
- Modify: `frontend/src/composables/useAssistant.js`
- Modify: `frontend/src/views/Assistant.vue`
- Test: `frontend/test/ai.test.js`

**Interfaces:**
- Consumes: SSE 的 `confirm` 事件（Task 6）与 `POST /api/ai/chat/resume`（Task 7）。
- Produces: `chatResume(payload, handlers)`，`payload` 形如 `{ conversationId, decision, clientRequestId }`。
- Produces: `consumeChatEvents` 在遇到 `confirm` 时返回 `{ status: 'confirming', kind, prompt, detail, conversationId }` 并停止读流。
- Produces: 助手消息的 `meta.status` 新增 `'confirming'`，`meta.confirm` 存放 `{ kind, prompt, detail }`。
- Produces: `useAssistant()` 返回值新增 `confirmPending(message)` 与 `rejectPending(message)` 两个方法。

- [ ] **Step 1: 写失败的测试**

`frontend/test/ai.test.js` 用的是 Node 内置测试运行器（`node:test` + `node:assert/strict`），不是 vitest，也没有 `describe` / `expect`。顶部已经 import 过 `consumeChatEvents`，不要重复 import。在文件末尾追加：

```javascript
test('confirm event ends the stream as a pending confirmation', async () => {
  const result = await consumeChatEvents([
    { type: 'status', content: '正在分析您的问题…' },
    {
      type: 'confirm',
      conversationId: 'conversation-1',
      kind: 'registration_create',
      prompt: '请确认是否为您挂 2026-09-04 下午 内科 张伟 的号',
      detail: { scheduleId: 9, staffName: '张伟', registerFee: '50.00' },
    },
  ])

  assert.equal(result.status, 'confirming')
  assert.equal(result.kind, 'registration_create')
  assert.equal(result.detail.staffName, '张伟')
  assert.equal(result.conversationId, 'conversation-1')
})

test('confirm event is not treated as an unexpected end of stream', async () => {
  const result = await consumeChatEvents([
    { type: 'confirm', kind: 'registration_cancel', prompt: '请确认是否退号', detail: {} },
  ])

  assert.equal(result.status, 'confirming')
  assert.equal(result.prompt, '请确认是否退号')
})

test('confirm event invokes the onConfirm handler', async () => {
  const seen = []
  await consumeChatEvents(
    [{ type: 'confirm', kind: 'registration_create', prompt: '请确认', detail: { scheduleId: 9 } }],
    { onConfirm: (payload) => seen.push(payload) },
  )

  assert.equal(seen.length, 1)
  assert.equal(seen[0].detail.scheduleId, 9)
})
```

- [ ] **Step 2: 跑测试确认失败**

```powershell
cd frontend
node --test test/ai.test.js
```

预期：三个新用例全部 FAIL——`confirm` 走到 `applyChatEvent` 的 `return null`，读完事件后 `finishStream` 因为 `acc.reply` 为空抛出「流式响应意外结束」。

- [ ] **Step 3: 加 confirm 分支与 chatResume**

在 `frontend/src/api/modules/ai.js` 里，把 `applyChatEvent` 的

```javascript
  if (event.type === 'done') {
```

之前插入：

```javascript
  if (event.type === 'confirm') {
    const confirming = {
      kind: event.kind,
      prompt: event.prompt || '请确认是否继续办理',
      detail: event.detail || {},
      conversationId: event.conversationId,
    }
    handlers.onConfirm?.(confirming)
    return { status: 'confirming', ...confirming }
  }
```

在文件末尾 `chatStream` 之后插入：

```javascript
export function chatResume(payload, handlers = {}) {
  return streamRequest(apiUrl('/api/ai/chat/resume'), payload, handlers)
}
```

- [ ] **Step 4: 跑前端测试确认通过**

```powershell
node --test test/ai.test.js
```

预期：全部 PASS。

- [ ] **Step 5: 在会话状态里挂起确认**

在 `frontend/src/composables/useAssistant.js` 的 import 区，把

```javascript
import { chatStream, deleteConversation, listCharges, listRegistrations } from '../api'
```

替换为：

```javascript
import { chatResume, chatStream, deleteConversation, listCharges, listRegistrations } from '../api'
```

`frontend/src/api/index.js` 是 `export * from './modules'`、`modules/index.js` 是 `export * from './ai'`，所以 Step 3 新增的 `chatResume` 会自动被再导出，不需要改桶文件。

在 `appendAssistantError` 之后插入：

```javascript
function markAssistantAwaitingConfirm(runtime, conversationId, requestId, confirming) {
  const request = runtime.requests.get(requestId)
  if (!request || request.status !== 'running') return
  request.status = 'confirming'
  updateAssistant(runtime, conversationId, requestId, (message) => ({
    ...message,
    content: confirming.prompt,
    meta: { ...message.meta, requestId, status: 'confirming', confirm: confirming },
  }))
  setRequestStatus(runtime, conversationId, requestId, 'confirming')
}
```

把 `createStreamHandlers` 里的

```javascript
    onDone: (result) => finalizeAssistantMessage(runtime, conversationId, requestId, result),
```

之前插入：

```javascript
    onConfirm: (confirming) => markAssistantAwaitingConfirm(runtime, conversationId, requestId, confirming),
```

- [ ] **Step 6: 加确认与取消两个动作**

在 `useAssistant.js` 的 `stopRequest` 函数之后插入：

```javascript
  async function respondToPending(message, decision) {
    const conversationId = runtime.activeId.value
    const requestId = createRequestId()
    // 确认卡片一旦作答就不再可点，避免重复提交。
    updateSession(runtime, conversationId, (session) => ({
      ...session,
      messages: session.messages.map((item) => (
        item.id === message.id
          ? { ...item, meta: { ...item.meta, status: 'completed', confirm: null } }
          : item
      )),
    }))
    const controller = new AbortController()
    runtime.requests.set(requestId, { conversationId, controller, status: 'running' })
    runtime.activeRequestId.value = requestId
    runtime.replying.value = true
    runtime.streaming.value = false
    runtime.streamStatus.value = null
    try {
      await chatResume(
        { conversationId, decision, clientRequestId: requestId },
        createStreamHandlers(runtime, conversationId, requestId),
      )
    } catch (nextError) {
      const request = runtime.requests.get(requestId)
      if (nextError.name === 'AbortError' && request?.status === 'stopped') return
      if (request?.status === 'running') {
        appendAssistantError(runtime, conversationId, requestId, nextError.code, nextError.message)
      }
    } finally {
      runtime.requests.delete(requestId)
      if (runtime.activeRequestId.value === requestId) {
        runtime.activeRequestId.value = null
        runtime.replying.value = false
        runtime.streaming.value = false
        runtime.streamStatus.value = null
      }
    }
  }
```

在 `useAssistant` 的 return 对象里，`stopReply` 那一行之后插入：

```javascript
    confirmPending: (message) => respondToPending(message, 'approve'),
    rejectPending: (message) => respondToPending(message, 'reject'),
```

- [ ] **Step 7: 允许 confirming 状态被持久化**

在 `frontend/src/features/assistant/session.js` 里，把

```javascript
const MESSAGE_STATUSES = new Set(['pending', 'streaming', 'completed', 'error', 'stopped'])
```

替换为：

```javascript
const MESSAGE_STATUSES = new Set(['pending', 'streaming', 'completed', 'error', 'stopped', 'confirming'])
```

- [ ] **Step 8: 渲染确认卡片**

在 `frontend/src/views/Assistant.vue` 的助手气泡里，把

```html
                  <CitationList v-if="message.sources?.length" :sources="message.sources" />
```

之前插入：

```html
                  <div v-if="message.meta?.confirm" class="chat-confirm">
                    <dl class="chat-confirm__detail">
                      <template v-for="(value, key) in confirmRows(message.meta.confirm.detail)" :key="key">
                        <dt>{{ key }}</dt>
                        <dd>{{ value }}</dd>
                      </template>
                    </dl>
                    <div class="chat-confirm__actions">
                      <button type="button" class="chat-confirm__cancel" @click="assistant.rejectPending(message)">再想想</button>
                      <button type="button" class="chat-confirm__ok" @click="assistant.confirmPending(message)">确认办理</button>
                    </div>
                  </div>
```

在该组件的 `<script setup>` 里追加：

```javascript
const CONFIRM_FIELD_LABELS = {
  deptName: '科室',
  staffName: '医生',
  workDate: '日期',
  timePeriod: '时段',
  remainingCount: '剩余号源',
  registerFee: '挂号费',
  regNo: '挂号单号',
  regFee: '挂号费',
}

/** 只展示患者看得懂的字段，scheduleId / registrationId 这类内部 id 不上卡片。 */
function confirmRows(detail) {
  const rows = {}
  for (const [key, label] of Object.entries(CONFIRM_FIELD_LABELS)) {
    const value = detail?.[key]
    if (value !== null && value !== undefined && value !== '') rows[label] = value
  }
  return rows
}
```

在该组件的 `<style scoped>` 里追加：

```css
.chat-confirm {
  margin-top: 12px;
  padding: 12px 14px;
  border: 1px solid var(--line, #e5e7eb);
  border-radius: 12px;
  background: var(--surface-2, #f8fafc);
}

.chat-confirm__detail {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 4px 16px;
  margin: 0 0 12px;
}

.chat-confirm__detail dt {
  color: var(--text-muted, #6b7280);
}

.chat-confirm__detail dd {
  margin: 0;
  font-weight: 600;
}

.chat-confirm__actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}

.chat-confirm__actions button {
  padding: 6px 16px;
  border-radius: 999px;
  border: 1px solid var(--line, #e5e7eb);
  cursor: pointer;
}

.chat-confirm__ok {
  background: var(--brand, #0f766e);
  border-color: transparent;
  color: #fff;
}
```

- [ ] **Step 9: 跑前端全量测试**

```powershell
npm run test
```

预期：全部 PASS。

- [ ] **Step 10: 提交**

```powershell
cd ..
git add frontend/src/api/modules/ai.js frontend/src/composables/useAssistant.js frontend/src/features/assistant/session.js frontend/src/views/Assistant.vue frontend/test/ai.test.js
git commit -m "feat(assistant): 聊天内渲染挂号确认卡片并支持确认后继续办理"
```

---

## 完成标准

- [ ] `mvn -o test` 全绿（在 `backend-java/` 下）
- [ ] `python -m pytest` 全绿（在 `ai-python/` 下）
- [ ] `npm run test` 全绿（在 `frontend/` 下）
- [ ] 八次提交各自独立，每次都能单独回滚
- [ ] 端到端手工验收（需要同时起 MySQL、Redis、Java、Python、前端）：
  - [ ] 患者说「帮我挂明天下午张伟的号」→ 出现确认卡片，卡片上的医生、日期、时段、挂号费与挂号页面显示的一致
  - [ ] 点「确认办理」→ 助手回复挂号已办好；到挂号列表页能看到这张单；`schedule.remaining_count` 减 1
  - [ ] 点「再想想」→ 助手回复没有提交；数据库里没有新单；`remaining_count` 不变
  - [ ] 确认卡片停留 6 分钟以上（超过委托令牌 5 分钟 TTL）再点确认，仍能成功
  - [ ] 连点两次「确认办理」→ 只产生一张挂号单（幂等键生效）
  - [ ] 患者说「把我明天那个号退了」→ 确认后号退掉，`remaining_count` 加 1
  - [ ] 关掉记忆开关后说「帮我挂号」→ 助手只列号源并引导去挂号页面，不弹确认卡片、不报错

## 不在本计划范围内

- `tool_node` 里同步 `agent.invoke()` 阻塞 async 事件循环——改成 `ainvoke` 需要同步调整 `test_tool_node.py` 里的 FakeAgent，单独立项
- 改期（退掉旧号并挂新号的原子操作）
- 确认卡片支持「编辑」再提交（`interrupt()` 目前只接受 `approve` / `reject`）
- 扩展只读工具（收费项目价格、我的费用清单、我的就诊与处方记录）——这些需要先核查 `/api/charges`、`/api/prescriptions`、`/api/visits` 现有的患者归属校验是否到位
- 把缺失的 `mvnw` / `mvnw.cmd` 补进仓库，消除对本机 Maven 缓存路径的依赖
- `chat_messages` 里为确认轮增加结构化的 `meta` 列（当前只落确认提示语文本）
