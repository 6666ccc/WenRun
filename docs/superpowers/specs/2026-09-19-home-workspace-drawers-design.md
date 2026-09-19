# 首页工作台：业务功能改为抽屉 — 设计文档

日期：2026-09-19
范围：`frontend/`（患者端 PC）。移动端行为不变。
前置：`2026-09-19-home-assistant-merge-design.md`（首页 = AI 健康助手）。

## 1. 目标

PC 端一切围绕首页（聊天）展示。点击"预约挂号 / 个人中心 / 挂号详情"不再跳到 `AppShell` 独立页面，而是在首页右侧以宽抽屉打开；关闭抽屉回到聊天。

已确认的取舍：

- 呈现方式：右侧宽抽屉（`min(720px, calc(100% - 40px))`），带遮罩，与现有"就诊资料"抽屉同一套交互。
- 地址栏：保留现有路径 `/registration`、`/registration/:id`、`/user`；PC 上渲染为"首页 + 抽屉"，浏览器后退 = 关闭抽屉。

## 2. 路由

`/home`、`/registration`、`/registration/:id`、`/user` 四条路由全部指向 `views/PatientWorkspace.vue`，`meta: { patient: true }` 不变。同一组件跨路由复用，切换抽屉时聊天区不重挂载。

`features/experience/workspace.js` 新增纯函数：

```js
workspacePanelFor(path, params) // -> { kind: 'registration' } | { kind: 'record', id } | { kind: 'user' } | null
```

## 3. `PatientWorkspace.vue`

- PC（`useIsPc()`）：渲染 `<Assistant />` + `<SideDrawer :open="Boolean(panel)">`，抽屉内容按 `panel.kind` 切换 `RegistrationBooking` / `RegistrationRecord` / `UserProfile`。
- 移动端：`/home` 渲染 `<Assistant />`；其他路径渲染原独立页 `Registration.vue` / `RegistrationDetail.vue` / `User.vue`。
- 抽屉标题：预约挂号 / 挂号详情 / 个人中心。挂号详情抽屉显示"返回个人中心"（`router.push('/user')`）。
- 关闭：`window.history.state?.back` 以 `/home` 开头时 `router.back()`，否则 `router.replace('/home')`。
- `RegistrationRecord` 取消成功 emit `cancelled` → `router.replace('/user')`。

## 4. `components/SideDrawer.vue`

Props：`open: Boolean`、`title: String`、`backLabel: String`（可选）。Events：`close`、`back`。

- `Teleport to="body"`；遮罩 `z-index: 60`，面板 `z-index: 61`（高于 AssistantShell 的 40）。
- 打开时锁 `body.overflow`、记录并在关闭时归还焦点；Esc 关闭；Tab 在面板内循环。
- 内容区 `overflow: auto`，内边距 24px；`prefers-reduced-motion` 下无过渡。

## 5. 内容组件抽取

| 原页面 | 新组件 | 接口 |
| --- | --- | --- |
| `Registration.vue` | `components/workspace/RegistrationBooking.vue` | 无 props |
| `RegistrationDetail.vue` | `components/workspace/RegistrationRecord.vue` | prop `id`；emits `cancelled`、`back` |
| `User.vue` | `components/workspace/UserProfile.vue` | 无 props |

- 三个 view 变为"`AppShell` + `PageHeader` + 内容组件"的薄壳，仅移动端使用。
- 内容组件内的弹窗（核对挂号信息、修改号源、`ConfirmDialog`）包 `Teleport to="body"`，避免被抽屉的 `transform` 变成定位祖先。
- `RegistrationRecord` 内的"返回个人中心"按钮 emit `back`；取消挂号成功 emit `cancelled`，不再自行 `router.replace`。
- 组件内 `RouterLink`（详情 / 去预约挂号）保持不变。

## 6. 清理

- 删除 `Assistant.vue` 的"健康服务"任务弹层（`assistant-task-overlay` 及样式、`taskPanel`、`onTaskKeydown`、相关 `watch`）；`openTask(task)` 简化为按类型 `router.push`。
- `useAssistant` 删除 `task`、`openTask`、`closeTask`；删除 `features/assistant/task.js` 及其测试。
- `Assistant.vue` 的 `prompt` 处理从 `onMounted` 改为 `watch(() => route.query.prompt, ..., { immediate: true })`，仅在 `route.path === '/home'` 时生效（组件跨路由复用后 `onMounted` 只跑一次）。

## 7. 测试

- `test/experience.test.js`：`workspacePanelFor` 四种输入；删除 `toTask` 测试。
- `test/shell.test.js`：四条路由均指向 `PatientWorkspace.vue`。
- `npm test` / `npm run lint` / `npm run build`；无头浏览器截 PC 三个抽屉 + 移动端挂号页。
