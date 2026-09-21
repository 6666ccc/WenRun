# 患者个人档案独立页 — 设计文档

日期：2026-09-19
范围：`frontend/`（患者端）。不改后端、不加表、不改 AI 服务。

## 1. 背景与目标

现状：个人资料、健康档案、挂号记录挤在 `/user` 的 `UserProfile.vue` 里。PC 上该路径是首页聊天的右侧抽屉，装不下「左栏资料卡 + 多 Tab」的档案工作台。

目标：按产品图做独立全页「个人档案」。有库表的字段接现有接口；没有的模块做套壳，并标明「数据库还未设计」。

已确认的取舍：

- 路由方案 C：独立全页，不进首页聊天抽屉。
- `/user` 重定向到 `/archive`，导航文案改为「个人档案」。
- 旧个人中心界面整页删除，不保留入口、不保留两套 UI。
- 健康趋势不用现有快照凑合画，整块套壳。
- 本次不加表、不改后端。快照接口可以留着，新页不展示快照列表。

## 2. 路由与导航

| 路径 | 变化 |
| --- | --- |
| `/archive` | 新增。渲染 `PatientArchive.vue`，`meta: { patient: true }`。**不**走 `PatientWorkspace.vue`。 |
| `/user` | 改为 `redirect: '/archive'`。 |
| `/home`、`/registration`、`/registration/:id` | 不变，仍走工作台（PC 抽屉 / 移动端独立页）。 |

在 `features/experience/mode.js`（或与现有 redirect 函数同文件）增加：

```js
export function userArchiveRedirect() {
  return '/archive'
}
```

路由表 `/user` 使用该 redirect。旧链接、助手「查看记录」入口、挂号详情返回都会落到新页。

### 2.1 导航文案与目标

三处主导航统一为：

```js
{ to: '/archive', icon: 'user', label: '个人档案' }
```

改动文件：`AppShell.vue`、`MobileTabbar.vue`、`AssistantShell.vue`。`AppShell` 账号行副文案由「查看个人中心」改为「查看个人档案」，链接改为 `/archive`。

### 2.2 工作台不再承载个人中心

`workspacePanelFor` 删除 `/user` 分支和 `WORKSPACE_TITLES.user`。`PatientWorkspace.vue` 删除 `User.vue` / `UserProfile.vue` 引用，以及 `panel.kind === 'user'` 的抽屉内容。挂号详情抽屉的返回目标改为 `/archive?tab=registrations`，返回按钮文案改为「个人档案」。

助手任务入口 `Assistant.vue` 的 `openTask`：`records` 类型改为 `router.push('/archive?tab=registrations')`。

`RegistrationDetail.vue`、`RegistrationRecord.vue` 中「返回个人中心」同步改为「返回个人档案」，目标 `/archive?tab=registrations`。挂号确认文案里的「个人中心」改为「个人档案」。

### 2.3 Tab 深链

`/archive?tab=` 合法值：`basic` | `health` | `activity` | `documents` | `history` | `registrations`。缺省或非法值视为 `health`（与产品图默认「健康数据」一致）。切换 Tab 用 `router.replace` 更新 query，不新增历史。

## 3. 页面结构

新页 `frontend/src/views/PatientArchive.vue`，外包 `AppShell`（现有患者服务侧栏 + 顶栏）。PC / 移动端都是这一页，不再经工作台分叉。

视觉对齐产品图，颜色与间距用现有 clinic token（`--color-bg`、`--color-brand-*`、`--color-mint-*`），不引入新色板。

### 3.1 布局

- 左栏：头像首字、姓名、性别 · 年龄、患者编号；手机 / 身份证 / 出生日期 / 地址 / 过敏史；「查看完整资料」切到 `tab=basic`。其下快捷操作。底部保留数据保护说明（静态文案，不接接口）。
- 右栏：Tab 条 + 当前 Tab 内容。
- 移动端（≤ 767px）：左栏叠在 Tab 上方，快捷操作可折行。不另做一套交互。

退出登录只留在 `AppShell` / `AssistantShell`，档案左栏不再放退出按钮。

### 3.2 快捷操作

| 操作 | 行为 |
| --- | --- |
| 预约挂号 | `router.push('/registration')`（PC 仍会进入聊天上的挂号抽屉，本次不改挂号外壳） |
| 填写健康档案 | `tab=history` |
| 上传健康数据 | 不可用，标明「数据库还未设计」 |
| 上传就医资料 | 不可用，标明「数据库还未设计」 |

### 3.3 Tab 内容

| Tab | query | 内容 |
| --- | --- | --- |
| 基本资料 | `basic` | 现有患者字段的查看 / 编辑表单（从旧 `UserProfile` 迁入） |
| 健康数据 | `health` | 见 4.2。默认 Tab |
| 运动睡眠 | `activity` | 整页套壳 |
| 就医资料 | `documents` | 整页套壳（病历 / 报告单 / 药物 / 体检报告四宫格也套壳） |
| 健康信息 | `history` | 既往史 / 家族史 / 个人史查看与编辑 |
| 我的挂号 | `registrations` | 现有挂号列表、取消、进详情 |

健康数据 Tab 内部仍展示「就医资料」「健康信息」摘要卡（与产品图一致）：有数据的摘要可点进对应 Tab；无库的就医资料摘要为套壳。底部「健康趋势」整块套壳，含近 7 天 / 30 天 / 近半年 / 近 1 年按钮，均不可用。

## 4. 组件划分

| 文件 | 职责 |
| --- | --- |
| `views/PatientArchive.vue` | AppShell、拉数、Tab 状态、把数据传给子组件 |
| `components/archive/ArchiveSidebar.vue` | 左栏资料卡 + 快捷操作 |
| `components/archive/ArchiveHealthData.vue` | 健康数据 Tab（体型、体征、摘要、趋势壳） |
| `components/archive/ArchiveBasicInfo.vue` | 基本资料查看 / 编辑 |
| `components/archive/ArchiveHealthInfo.vue` | 三病史查看 / 编辑 |
| `components/archive/ArchiveRegistrations.vue` | 我的挂号列表（从旧页迁入取消/详情逻辑） |
| `components/archive/ArchiveUnavailable.vue` | 统一套壳：标题 + 文案「数据库还未设计」 |

套壳出现在：未建库指标卡、运动睡眠 Tab、就医资料 Tab、健康趋势、两个上传快捷操作。文案固定为「数据库还未设计」，样式用 warning token，不假装成可填写表单。

## 5. 数据

进入页面后 `Promise.allSettled` 并行请求，一块失败不空白整页：

- `getPatient(patientId)` → 左栏 + 基本资料
- `getHealthProfile(patientId)` → 健康数据已接字段 + 健康信息
- `listRegistrations({ userId })` → 我的挂号

不请求快照列表。未绑定 `patientId` 时展示空态「暂无患者档案」，不发健康/挂号请求。

### 5.1 接现有接口

| UI | 来源 |
| --- | --- |
| 姓名、性别、手机、身份证、出生日期、地址、过敏史、患者编号 | `patient` |
| 年龄 | 由 `birthDate` 计算；无出生日期则显示「—」 |
| 身高、体重、血压、血糖、心率、测量时间 | `patient_health_profile` |
| BMI | `calcBmi(heightCm, weightKg)`，已有工具函数 |
| 既往史、家族史、个人史 | 同上表 |
| 挂号列表 | `registration` |

编辑：

- 基本资料：沿用 `updatePatient` + `updateProfile`（与旧页相同容错：后者失败不回滚前者）。
- 体征与病史：沿用 `createHealthProfile` / `updateHealthProfile`，payload 仍是整份当前值（`toHealthPayload`），不新增按指标接口。点击已接指标的「+ / 记录数据」打开该组字段的编辑态，保存时带上未改的其余字段。

身份证号展示继续脱敏（旧 `maskedIdCard` 逻辑迁入基本资料组件）。

### 5.2 套壳（标明「数据库还未设计」）

- 腰围、WHtR
- 血氧、呼吸、体温
- 运动睡眠整 Tab
- 就医资料整 Tab 及健康数据里的就医资料四宫格（病历 / 报告单 / 药物 / 体检报告）
- 健康趋势及时间范围切换
- 快捷操作「上传健康数据」「上传就医资料」

这些控件禁用或点击后只提示套壳文案，不发请求、不写 localStorage 假数据。

## 6. 删除

- `frontend/src/views/User.vue`
- `frontend/src/components/workspace/UserProfile.vue`
- `PatientWorkspace.vue` 中个人中心抽屉分支
- 导航与文案中的「个人中心」指向（改为「个人档案」）

保留：`api/modules/healthProfile.js`、`utils/healthProfile.js`、后端健康档案接口与快照表。新页不调用 `listHealthSnapshots` / `deleteHealthSnapshot` / `deleteHealthProfile`。

## 7. 错误处理

- 患者档案失败：主区域 `UiState` 错误，左栏不展示假资料。
- 健康档案失败：健康数据 / 健康信息显示该块错误文案，基本资料和挂号仍可用。
- 挂号失败：仅「我的挂号」显示错误。
- 未登录：现有路由守卫去 `/login`，不变。
- 套壳模块不进入错误态。

## 8. 测试

- `test/experience.test.js`：`workspacePanelFor('/user')` 改为断言 `null`（redirect 发生在路由层，工作台不再映射该路径）；新增 `userArchiveRedirect()` → `'/archive'`。
- `test/shell.test.js`：工作台路由列表去掉 `/user`，增加 `/archive` 指向 `PatientArchive.vue`；`/user` 断言为 redirect。导航断言 `to: '/archive'` 且文案「个人档案」。删除对 `User.vue` / 工作台内 `UserProfile` 的断言。
- `test/health-profile.test.js`：工具函数测试保留。
- 源码断言：`PatientArchive.vue`（或套壳组件）包含「数据库还未设计」；不包含快照列表相关调用。
- 运行 `npm test`；若有 `npm run lint` / `npm run build` 一并跑。
- 手动：PC 与 < 768px 打开 `/archive`、`/user` 重定向、Tab 切换与 query、已接字段读写、套壳点击无请求、从挂号详情返回到「我的挂号」。

## 9. 不在范围内

- 后端、数据库、快照 API 行为。
- 挂号页 / 挂号详情改为 AppShell 全页。
- 医生端或其他 portal。
- 真实文件上传、运动睡眠采集、分指标时序图。
