# 首页与 AI 健康助手合并 — 设计文档

日期：2026-09-19
范围：`frontend/`（患者端），不涉及后端与 AI 服务。

## 1. 背景与目标

现状：`/home`（`Home.vue`）只是助手的入口页，页面上的所有按钮最终都跳转到 `/assistant` 并携带 `prompt`；`/assistant`（`Assistant.vue`）是完整聊天页。两页各用一套外壳（`AppShell` / `AssistantShell`），主导航 4 项。

目标：把首页与助手合并为一个"聊天优先"的首页。进入 `/home` 直接是对话界面，原首页的欢迎语、下次就诊、常用任务、今日号源成为对话的欢迎空状态；一发消息即进入聊天流。主导航减为 3 项。

已确认的取舍：

- 页面形态：聊天优先（不是首页卡片 + 内嵌聊天，也不是左右分栏）。
- PC 外壳：沿用 `AssistantShell`（方案 A），业务页继续用 `AppShell`。
- 进入 `/home` 时恢复上次活动会话；该会话无消息时显示欢迎空状态。
- 移动端 Tabbar 3 项：首页 / 挂号 / 个人中心。
- 不在聊天顶栏新增"急症请拨打 120"徽标。

## 2. 路由

| 路径 | 变化 |
| --- | --- |
| `/home` | 渲染合并后的 `Assistant.vue`。`meta` 保持 `{ patient: true }`。 |
| `/assistant` | 改为重定向到 `/home`，原样携带 `query`（含 `prompt`、`preview`）。 |
| 其他 | 不变。`patientHomePath()` 仍返回 `/home`。 |

实现：在 `features/experience/mode.js` 新增纯函数

```js
export function assistantRedirect(to) {
  return { path: '/home', query: to.query }
}
```

路由表中 `/assistant` 使用 `redirect: assistantRedirect`。`router.beforeEach` 里的 dev 预览白名单只保留 `/home`（重定向发生在守卫之前，`/assistant?preview=1` 仍可用）。

`Assistant.vue` 内 `onMounted` 处理 `prompt` 后的 `router.replace` 目标改为 `/home`。

## 3. 欢迎空状态：`AssistantWelcome.vue`

新建 `frontend/src/components/AssistantWelcome.vue`，替换 `Assistant.vue` 现有的 `.chat-empty` 块。仅在 `!hasMessages` 时渲染。

### 3.1 内容（自上而下）

1. 日期时间行 + 标题 `「{姓名}，今天想先了解什么？」`（沿用 Home 的 `formatDate` / `formatTime`）。
2. "下次就诊"条：有待就诊预约时显示 `formatVisitSchedule(workDate, timePeriod) · 科室 · 医生`，点击跳 `/registration/:id`；无预约显示"暂无待就诊预约"，点击跳 `/registration`；请求失败显示"就诊信息暂时无法获取"。
3. 常用任务 chip ×3：帮我挂号 / 查预约 / 找科室，文案与 prompt 沿用 `Home.vue` 的 `agentActions`。
4. "今日可预约"列表：最多 3 条，每条显示科室 · 医生 / 时段 · 挂号费 / 余号；右上角"全部号源"链接到 `/registration`。空态与失败文案沿用 Home。

推荐问题（4 条）与输入框仍由 `Assistant.vue` 的 footer 渲染，不进入该组件。

### 3.2 数据

- 下次就诊：`props.appointments`（父组件传入 `assistant.context.value.appointments`）与 `props.appointmentsError`。取 `status === 1` 的第一条。不再重复请求。
- 今日号源：组件自身 `onMounted` 调用 `listSchedules({ workDate: todayISO() })`，过滤 `remainingCount > 0 && isBookableSchedule(workDate, timePeriod)`，`slice(0, 3)`。失败置 `scheduleError = true`。
- 用户姓名：`useAuth().user`。
- dev 预览：`import.meta.env.DEV && route.query.preview === '1'` 时使用 Home 现有的 `previewData`，不发请求。

### 3.3 事件

- `emit('prompt', text)`：常用任务 chip、号源行点击时触发；父组件调用 `send(text)` 直接发消息，不再路由跳转。
- 下次就诊条、全部号源链接直接用 `router` / `RouterLink` 跳转。

### 3.4 样式

从 `Home.vue` 迁移 `visit-strip`、`agent-action-grid`（改为横向 chip）、`schedule-stack`、`agent-panel__heading` 相关样式到该组件的 scoped style，宽度跟随 `.chat-main__inner`（960px 列）。移动端（≤ 767px）单列、缩小间距。

## 4. 外壳与导航

### 4.1 `AssistantShell.vue`

- 侧栏底部 `assistant-shell__sidebar-foot` 内容替换为：
  - 导航两项：`预约挂号 → /registration`、`个人中心 → /user`（`RouterLink`，图标 `calendar` / `user`）。
  - 账号行：头像首字 + 姓名 + "退出登录"按钮（`useAuth().logout()` 后 `router.replace('/login')`）。
- 品牌区按钮不再跳转（已在首页），改为纯展示或点击无操作；`goHome` 删除。
- 移动端（< 768px）：`.assistant-shell` 高度改为 `100dvh` 且底部预留 Tabbar 高度（`padding-bottom: calc(64px + env(safe-area-inset-bottom))`），输入框位于 Tabbar 之上。
- 抽屉逻辑、就诊资料面板不变。

### 4.2 `Assistant.vue`

- 在 `AssistantShell` 之后渲染 `<MobileTabbar v-if="!isPc" />`（`useIsPc`）。
- 用 `AssistantWelcome` 替换 `.chat-empty`，监听 `@prompt="send"`。
- `onMounted` 中 `router.replace` 目标改为 `/home`。
- 其余逻辑（会话、确认卡片、任务弹层、快速模式）不变。

### 4.3 `AppShell.vue`

`nav` 数组去掉 `{ to: '/assistant', label: 'AI 健康助手' }`，保留首页 / 预约挂号 / 个人中心。其他不变。

### 4.4 `MobileTabbar.vue`

```js
const tabs = [
  { to: '/home', icon: 'ai', label: '首页' },
  { to: '/registration', icon: 'calendar', label: '挂号' },
  { to: '/user', icon: 'user', label: '个人中心' },
]
```

去掉 `featured` 字段与中间突出样式（`.mobile-tabbar__item--featured` 相关 CSS 一并删除）。

## 5. 删除

- `frontend/src/views/Home.vue`。
- `AssistantShell.vue` 中 `goHome`、`assistant-shell__home` 按钮及样式。
- `clinic-theme.css` 中 `.mobile-tabbar__item--featured*` 规则。

## 6. 错误处理

- 号源 / 预约请求失败：欢迎区对应区块显示"暂时无法获取"文案，不阻塞聊天。
- 会话加载失败：沿用 `assistant.sessionError` 现有展示。
- 未登录访问 `/home`：路由守卫重定向 `/login`，不变。

## 7. 测试

- `test/experience.test.js`：新增 `assistantRedirect` 测试——`/assistant?prompt=x&preview=1` → `{ path: '/home', query: { prompt: 'x', preview: '1' } }`；无 query 时 `query` 为空对象。
- `test/shell.test.js`：新增断言 `AppShell.vue` 源码不包含 `to: '/assistant'`；`MobileTabbar.vue` 源码包含 3 个 `to:` 且不含 `featured`。
- 手动验证：PC 与 < 768px 两种宽度下 `/home` 的空状态、发消息后的聊天流、`/assistant?prompt=你好` 重定向并自动发送、Tabbar 切换、侧栏底部导航与退出登录。
- 运行 `npm test`、`npm run lint`（若脚本存在）、`npm run build`。

## 8. 不在范围内

- 后端 / AI 服务接口。
- 医生端或其他 portal。
- `Registration.vue`、`User.vue` 页面内容。
