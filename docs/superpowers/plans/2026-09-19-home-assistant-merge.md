# 首页与 AI 健康助手合并 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 `/home` 直接成为聊天优先的 AI 健康助手页，原首页内容变为对话欢迎空状态，导航减为 3 项，`/assistant` 重定向到 `/home`。

**Architecture:** 保留 `Assistant.vue` + `AssistantShell.vue` 作为首页骨架；新增 `AssistantWelcome.vue` 承接原 `Home.vue` 的欢迎/就诊/常用任务/号源内容，纯数据逻辑抽到 `features/home/overview.js`；`AssistantShell` 侧栏底部改为业务导航 + 账号；路由把 `/home` 指向 `Assistant.vue`，`/assistant` 通过 `assistantRedirect` 带 query 重定向；删除 `Home.vue`。

**Tech Stack:** Vue 3 `<script setup>`、vue-router 4、Vite、`node --test`（`frontend/test/*.test.js`）、ESLint。

**Spec:** `docs/superpowers/specs/2026-09-19-home-assistant-merge-design.md`

## Global Constraints

- 只改 `frontend/`，不改后端与 AI 服务。
- 所有命令在 `frontend/` 目录执行：`npm test`、`npm run lint`、`npm run build`。基线：36 个测试通过、lint 无输出。
- 文案：导航统一使用「首页 / 预约挂号 / 个人中心」，移动端 Tabbar 使用「首页 / 挂号 / 个人中心」。
- 不在聊天顶栏新增"急症请拨打 120"徽标。
- `patientHomePath()` 保持返回 `/home`。
- 移动端断点：Tabbar 显示条件为 `< 768px`（`useIsPc`）；`AssistantShell` 抽屉断点 `≤ 959px` 保持不变。
- 提交信息用中文，前缀沿用仓库习惯（`feat:` / `refactor:` / `test:`）。

---

## File Structure

| 文件 | 操作 | 职责 |
| --- | --- | --- |
| `frontend/src/features/experience/mode.js` | 修改 | 新增 `assistantRedirect(to)` 纯函数 |
| `frontend/src/features/home/overview.js` | 新建 | `nextAppointment(registrations)`、`bookableToday(schedules, limit, now)` 纯函数 |
| `frontend/src/components/AssistantWelcome.vue` | 新建 | 欢迎空状态 UI：欢迎语、下次就诊、常用任务、今日号源；`emit('prompt')` |
| `frontend/src/components/AssistantShell.vue` | 修改 | 侧栏底部改为业务导航 + 账号；移动端为 Tabbar 留位 |
| `frontend/src/views/Assistant.vue` | 修改 | 使用 `AssistantWelcome`，移动端渲染 `MobileTabbar`，`router.replace` 目标改 `/home` |
| `frontend/src/router/index.js` | 修改 | `/home` → `Assistant.vue`，`/assistant` → `assistantRedirect` |
| `frontend/src/components/AppShell.vue` | 修改 | 主导航减为 3 项 |
| `frontend/src/components/MobileTabbar.vue` | 修改 | 3 项，去掉 featured |
| `frontend/src/styles/clinic-theme.css` | 修改 | 删除 `.mobile-tabbar__item--featured*` |
| `frontend/src/views/Home.vue` | 删除 | 被合并 |
| `frontend/test/experience.test.js` | 修改 | `assistantRedirect`、`overview` 测试 |
| `frontend/test/shell.test.js` | 修改 | 导航源码断言 |

---

### Task 1: `assistantRedirect` 纯函数

**Files:**
- Modify: `frontend/src/features/experience/mode.js`
- Test: `frontend/test/experience.test.js`

**Interfaces:**
- Produces: `assistantRedirect(to: { query?: object }) => { path: '/home', query: object }`，Task 5 的路由表使用。

- [ ] **Step 1: 写失败测试**

在 `frontend/test/experience.test.js` 顶部 import 行改为：

```js
import { assistantRedirect, patientHomePath, isPatientPortal } from '../src/features/experience/mode.js'
```

文件末尾追加：

```js
test('assistantRedirect folds the legacy assistant route into home and keeps query', () => {
  assert.deepEqual(
    assistantRedirect({ path: '/assistant', query: { prompt: '你好', preview: '1' } }),
    { path: '/home', query: { prompt: '你好', preview: '1' } },
  )
  assert.deepEqual(assistantRedirect({ path: '/assistant', query: {} }), { path: '/home', query: {} })
  assert.deepEqual(assistantRedirect({ path: '/assistant' }), { path: '/home', query: {} })
})
```

- [ ] **Step 2: 运行确认失败**

Run: `cd frontend; npm test`
Expected: 失败，报错含 `assistantRedirect is not a function` 或 `does not provide an export named 'assistantRedirect'`。

- [ ] **Step 3: 实现**

`frontend/src/features/experience/mode.js` 末尾追加：

```js
/** 旧的 /assistant 路径统一并入首页，保留 prompt / preview 等 query。 */
export function assistantRedirect(to) {
  return { path: '/home', query: { ...(to?.query || {}) } }
}
```

- [ ] **Step 4: 运行确认通过**

Run: `cd frontend; npm test`
Expected: `pass 37`, `fail 0`。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/experience/mode.js frontend/test/experience.test.js
git commit -m "feat(home): 新增 assistantRedirect 将旧助手路径并入首页"
```

---

### Task 2: 首页概览纯函数 `features/home/overview.js`

**Files:**
- Create: `frontend/src/features/home/overview.js`
- Test: `frontend/test/experience.test.js`

**Interfaces:**
- Consumes: `isBookableSchedule(workDate, timePeriod, now)` from `frontend/src/utils/scheduleDate.js`。
- Produces:
  - `nextAppointment(registrations: Array) => object | null` — 第一条 `status === 1` 的挂号。
  - `bookableToday(schedules: Array, limit = 3, now = new Date()) => Array` — 余号 > 0 且 `isBookableSchedule` 为真的前 `limit` 条。

- [ ] **Step 1: 写失败测试**

`frontend/test/experience.test.js` 顶部 import 区追加：

```js
import { bookableToday, nextAppointment } from '../src/features/home/overview.js'
```

文件末尾追加：

```js
test('nextAppointment picks the first pending registration only', () => {
  const registrations = [
    { id: 1, status: 3, deptName: '已取消' },
    { id: 2, status: 1, deptName: '心内科' },
    { id: 3, status: 1, deptName: '呼吸内科' },
  ]
  assert.equal(nextAppointment(registrations)?.id, 2)
  assert.equal(nextAppointment([{ id: 9, status: 2 }]), null)
  assert.equal(nextAppointment(null), null)
})

test('bookableToday keeps only bookable schedules with remaining count and caps the list', () => {
  const now = new Date('2026-09-19T01:00:00Z') // 北京时间 09:00
  const schedules = [
    { id: 1, workDate: '2026-09-19', timePeriod: '上午', remainingCount: 8 },
    { id: 2, workDate: '2026-09-19', timePeriod: '下午', remainingCount: 0 },
    { id: 3, workDate: '2026-09-18', timePeriod: '上午', remainingCount: 5 },
    { id: 4, workDate: '2026-09-19', timePeriod: '下午', remainingCount: 2 },
    { id: 5, workDate: '2026-09-20', timePeriod: '上午', remainingCount: 1 },
    { id: 6, workDate: '2026-09-20', timePeriod: '下午', remainingCount: 1 },
  ]
  assert.deepEqual(bookableToday(schedules, 3, now).map((item) => item.id), [1, 4, 5])
  assert.deepEqual(bookableToday(undefined, 3, now), [])
})
```

- [ ] **Step 2: 运行确认失败**

Run: `cd frontend; npm test`
Expected: 失败，报错含 `Cannot find module` 且路径指向 `features/home/overview.js`。

- [ ] **Step 3: 实现**

新建 `frontend/src/features/home/overview.js`：

```js
import { isBookableSchedule } from '../../utils/scheduleDate'

const asList = (value) => (Array.isArray(value) ? value : [])

/** 首页"下次就诊"取第一条待就诊（status === 1）的挂号。 */
export function nextAppointment(registrations) {
  return asList(registrations).find((item) => Number(item?.status) === 1) || null
}

/** 首页"今日可预约"：有余号且未过时段截止的号源，最多 limit 条。 */
export function bookableToday(schedules, limit = 3, now = new Date()) {
  return asList(schedules)
    .filter((item) => Number(item?.remainingCount) > 0 && isBookableSchedule(item?.workDate, item?.timePeriod, now))
    .slice(0, limit)
}
```

- [ ] **Step 4: 运行确认通过**

Run: `cd frontend; npm test`
Expected: `pass 39`, `fail 0`。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/home/overview.js frontend/test/experience.test.js
git commit -m "feat(home): 抽出首页概览纯函数 nextAppointment / bookableToday"
```

---

### Task 3: 欢迎空状态组件 `AssistantWelcome.vue`

**Files:**
- Create: `frontend/src/components/AssistantWelcome.vue`

**Interfaces:**
- Consumes: Task 2 的 `nextAppointment`、`bookableToday`；`listSchedules({ workDate })` from `frontend/src/api`；`formatDate(v)`、`formatTime()`、`formatTimePeriod(period)`、`formatVisitSchedule(workDate, timePeriod)` from `frontend/src/utils`；`todayISO()` from `frontend/src/utils/scheduleDate`；`useAuth().user`。
- Produces: 组件 props `appointments: Array`、`appointmentsError: Boolean`；事件 `prompt(text: string)`。Task 4 在 `Assistant.vue` 中使用。

- [ ] **Step 1: 新建组件**

新建 `frontend/src/components/AssistantWelcome.vue`：

```vue
<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuth } from '../stores'
import { listSchedules } from '../api'
import { formatDate, formatTime, formatTimePeriod, formatVisitSchedule } from '../utils'
import { todayISO } from '../utils/scheduleDate'
import { bookableToday, nextAppointment } from '../features/home/overview'
import UiIcon from './UiIcon.vue'

const props = defineProps({
  appointments: { type: Array, default: () => [] },
  appointmentsError: { type: Boolean, default: false },
})
const emit = defineEmits(['prompt'])

const router = useRouter()
const route = useRoute()
const { user } = useAuth()
const visualPreview = import.meta.env.DEV && route.query.preview === '1'
const schedules = ref([])
const scheduleError = ref(false)

const name = computed(() => user.value?.realName || user.value?.username || '患者')
const next = computed(() => nextAppointment(props.appointments))
const appointmentSummary = computed(() => (next.value
  ? `${formatVisitSchedule(next.value.workDate, next.value.timePeriod)} · ${next.value.deptName} · ${next.value.staffName}`
  : (props.appointmentsError ? '就诊信息暂时无法获取' : '暂无待就诊预约')))

const agentActions = [
  { icon: 'calendar', label: '帮我挂号', prompt: '我想预约挂号，请帮我看看近期可用号源。' },
  { icon: 'record', label: '查预约', prompt: '帮我查看最近的预约和就诊安排。' },
  { icon: 'hospital', label: '找科室', prompt: '我不确定该挂什么科，请根据症状帮我判断。' },
]

const previewSchedules = [
  { id: 1, deptName: '心内科', staffName: '张医生', timePeriod: '上午', remainingCount: 8, registerFee: 30 },
  { id: 2, deptName: '呼吸内科', staffName: '李医生', timePeriod: '下午', remainingCount: 5, registerFee: 25 },
  { id: 3, deptName: '消化内科', staffName: '王医生', timePeriod: '上午', remainingCount: 12, registerFee: 25 },
]

function openVisit() {
  router.push(next.value ? `/registration/${next.value.id}` : '/registration')
}

onMounted(async () => {
  if (visualPreview) {
    schedules.value = previewSchedules
    return
  }
  try {
    schedules.value = bookableToday(await listSchedules({ workDate: todayISO() }))
  } catch {
    scheduleError.value = true
  }
})
</script>

<template>
  <section class="welcome" aria-label="首页概览">
    <div class="welcome__head">
      <p>{{ formatDate(new Date()) }} · {{ formatTime() }}</p>
      <h1>{{ name }}，今天想先了解什么？</h1>
    </div>

    <button
      class="visit-strip"
      type="button"
      :aria-label="next ? `查看下次就诊：${appointmentSummary}` : '开始预约挂号'"
      @click="openVisit"
    >
      <span class="visit-strip__icon"><UiIcon name="calendar" :size="20" /></span>
      <span class="visit-strip__body">
        <small>{{ next ? '下次就诊' : '就诊安排' }}</small>
        <strong>{{ appointmentSummary }}</strong>
      </span>
      <span class="visit-strip__action">{{ next ? '查看' : '去挂号' }}<UiIcon name="arrowRight" :size="16" /></span>
    </button>

    <div class="welcome__actions" aria-label="常用任务">
      <button v-for="action in agentActions" :key="action.label" type="button" @click="emit('prompt', action.prompt)">
        <UiIcon :name="action.icon" :size="16" />{{ action.label }}
      </button>
    </div>

    <section class="welcome__panel" aria-labelledby="welcome-schedule-title">
      <div class="welcome__panel-head">
        <div><span>实时信息</span><h2 id="welcome-schedule-title">今日可预约</h2></div>
        <RouterLink to="/registration">全部号源<UiIcon name="arrowRight" :size="16" /></RouterLink>
      </div>
      <p v-if="scheduleError" class="welcome__state">号源暂时无法获取，可让助手稍后再查。</p>
      <div v-else-if="schedules.length" class="schedule-stack">
        <button
          v-for="schedule in schedules"
          :key="schedule.id"
          type="button"
          @click="emit('prompt', `帮我看看${schedule.deptName}${schedule.staffName}的可预约时间。`)"
        >
          <span class="schedule-stack__icon"><UiIcon name="hospital" :size="18" /></span>
          <span><strong>{{ schedule.deptName }} · {{ schedule.staffName }}</strong><small>{{ formatTimePeriod(schedule.timePeriod) }} · 挂号费 ¥{{ schedule.registerFee }}</small></span>
          <b>余 {{ schedule.remainingCount }}</b>
        </button>
      </div>
      <p v-else class="welcome__state">今日暂无可预约号源，可让助手查询后续排班。</p>
    </section>
  </section>
</template>

<style scoped>
.welcome {
  --home-ink: #17343b;
  --home-muted: #60777d;
  --home-teal: #0f8f82;
  --home-aqua: #dff5f2;
  width: 100%;
  padding: 20px 0 8px;
  color: var(--home-ink);
}
.welcome__head p { margin: 0 0 5px; color: #5c7a7b; font-size: 12px; font-weight: 650; letter-spacing: .04em; }
.welcome__head h1 { margin: 0; color: #153b3c; font-size: clamp(26px, 3vw, 34px); font-weight: 750; line-height: 1.2; letter-spacing: -.03em; }

.visit-strip { width: 100%; min-height: 72px; display: grid; grid-template-columns: auto minmax(0,1fr) auto; align-items: center; gap: 13px; margin-top: 22px; padding: 11px 13px; border: 1px solid rgba(15, 143, 130, .2); border-radius: 18px; background: #f6fbfb; color: inherit; cursor: pointer; text-align: left; font: inherit; transition: border-color 160ms ease, box-shadow 160ms ease; }
.visit-strip:hover, .visit-strip:focus-visible { border-color: var(--home-teal); box-shadow: 0 10px 28px rgba(27, 78, 81, .1); }
.visit-strip__icon { width: 44px; height: 44px; display: grid; place-items: center; border-radius: 13px; background: var(--home-aqua); color: var(--home-teal); }
.visit-strip__body { min-width: 0; }
.visit-strip__body small, .visit-strip__body strong { display: block; }
.visit-strip__body small { margin-bottom: 4px; color: var(--home-muted); font-size: 11px; }
.visit-strip__body strong { overflow: hidden; font-size: 14px; text-overflow: ellipsis; white-space: nowrap; }
.visit-strip__action { display: inline-flex; align-items: center; gap: 2px; color: var(--home-teal); font-size: 12px; font-weight: 750; white-space: nowrap; }

.welcome__actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 18px; }
.welcome__actions button { display: inline-flex; align-items: center; gap: 8px; min-height: 40px; padding: 0 14px; border: 1px solid #d9e9e8; border-radius: 999px; background: #f7fbfb; color: var(--home-ink); cursor: pointer; font: inherit; font-size: 13px; font-weight: 650; transition: border-color 160ms ease, background-color 160ms ease; }
.welcome__actions button svg { color: var(--home-teal); }
.welcome__actions button:hover, .welcome__actions button:focus-visible { border-color: #73bdb5; background: #eef8f7; }

.welcome__panel { margin-top: 26px; }
.welcome__panel-head { display: flex; align-items: end; justify-content: space-between; gap: 12px; margin-bottom: 8px; }
.welcome__panel-head span { display: block; margin-bottom: 3px; color: var(--home-teal); font-size: 10px; font-weight: 800; letter-spacing: .11em; }
.welcome__panel-head h2 { margin: 0; color: var(--home-ink); font-size: 17px; }
.welcome__panel-head a { min-height: 36px; display: inline-flex; align-items: center; gap: 2px; color: var(--home-muted); font-size: 11px; font-weight: 700; white-space: nowrap; }

.schedule-stack { display: grid; }
.schedule-stack button { min-width: 0; min-height: 62px; display: grid; grid-template-columns: auto minmax(0,1fr) auto; align-items: center; gap: 10px; padding: 10px 0; border: 0; border-bottom: 1px solid #e1ebeb; background: transparent; color: inherit; cursor: pointer; font: inherit; text-align: left; }
.schedule-stack button:first-child { border-top: 1px solid #e1ebeb; }
.schedule-stack button:hover span:nth-child(2) strong, .schedule-stack button:focus-visible span:nth-child(2) strong { color: var(--home-teal); }
.schedule-stack__icon { width: 34px; height: 34px; display: grid; place-items: center; border-radius: 11px; background: #e9f6f4; color: var(--home-teal); }
.schedule-stack strong, .schedule-stack small { display: block; }
.schedule-stack strong { overflow: hidden; font-size: 13px; text-overflow: ellipsis; white-space: nowrap; }
.schedule-stack small { margin-top: 3px; color: var(--home-muted); font-size: 11px; }
.schedule-stack b { color: var(--home-teal); font-size: 11px; white-space: nowrap; }
.welcome__state { min-height: 62px; display: flex; align-items: center; margin: 0; color: var(--home-muted); font-size: 12px; line-height: 1.6; }

@media (max-width: 767px) {
  .welcome { padding-top: 12px; }
  .welcome__head h1 { font-size: 25px; }
  .visit-strip { min-height: 66px; margin-top: 18px; padding: 9px 10px; border-radius: 16px; }
  .visit-strip__icon { width: 40px; height: 40px; border-radius: 12px; }
  .visit-strip__body strong { font-size: 12px; }
  .visit-strip__action { font-size: 11px; }
}
@media (prefers-reduced-motion: reduce) {
  .visit-strip, .welcome__actions button { transition: none; }
}
</style>
```

- [ ] **Step 2: Lint**

Run: `cd frontend; npm run lint`
Expected: 无输出（组件未被引用也不会报 unused，ESLint 只检查文件内部）。

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/AssistantWelcome.vue
git commit -m "feat(home): 新增 AssistantWelcome 欢迎空状态组件"
```

---

### Task 4: `Assistant.vue` 接入欢迎组件与 Tabbar，`AssistantShell` 侧栏底部改造

**Files:**
- Modify: `frontend/src/views/Assistant.vue`
- Modify: `frontend/src/components/AssistantShell.vue`

**Interfaces:**
- Consumes: Task 3 的 `AssistantWelcome`（props `appointments`、`appointmentsError`，事件 `prompt`）；`MobileTabbar.vue`；`useIsPc()`；`useAuth().user / logout`。
- Produces: `/home` 可直接渲染的 `Assistant.vue`（Task 5 路由切换依赖）。

- [ ] **Step 1: 修改 `Assistant.vue` script**

import 区把

```js
import AssistantShell from '../components/AssistantShell.vue'
import UiIcon from '../components/UiIcon.vue'
import CitationList from '../components/CitationList.vue'
```

改为

```js
import { useIsPc } from '../composables/useIsPc'
import AssistantShell from '../components/AssistantShell.vue'
import AssistantWelcome from '../components/AssistantWelcome.vue'
import MobileTabbar from '../components/MobileTabbar.vue'
import UiIcon from '../components/UiIcon.vue'
import CitationList from '../components/CitationList.vue'
```

在 `const assistant = useAssistant(user)` 之后加一行：

```js
const isPc = useIsPc()
```

`onMounted` 中

```js
    router.replace({ path: '/assistant', query: visualPreview ? { preview: '1' } : {} })
```

改为

```js
    router.replace({ path: '/home', query: visualPreview ? { preview: '1' } : {} })
```

- [ ] **Step 2: 修改 `Assistant.vue` template**

把

```vue
          <div v-if="!hasMessages" class="chat-empty">
            <span class="chat-empty__mark" aria-hidden="true"><UiIcon name="logo" :size="32" /></span>
            <h1>你好，我是温润健康助手。</h1>
          </div>
```

改为

```vue
          <AssistantWelcome
            v-if="!hasMessages"
            :appointments="assistant.context.value.appointments"
            :appointments-error="Boolean(assistant.context.value.errors.appointments)"
            @prompt="send"
          />
```

在 `</AssistantShell>` 之后、`<Teleport to="body">` 之前插入：

```vue
  <MobileTabbar v-if="!isPc" />
```

- [ ] **Step 3: 删除 `Assistant.vue` 中无用样式**

删除以下三个规则块（`.chat-empty`、`.chat-empty__mark`、`.chat-empty h1`），以及移动端媒体查询里的 `.chat-empty h1 { font-size: 26px; }` 一行：

```css
.chat-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: 1;
  padding: 12px 12px 24px;
  text-align: center;
}

.chat-empty__mark {
  width: 64px;
  height: 64px;
  display: grid;
  place-items: center;
  margin-bottom: 20px;
  border-radius: 18px;
  background: var(--color-brand-800);
  color: #fff;
}

.chat-empty h1 {
  max-width: 18em;
  margin: 0;
  color: #1a1a1a;
  font-size: clamp(28px, 3.6vw, 36px);
  font-weight: 600;
  letter-spacing: -.04em;
  line-height: 1.3;
}
```

- [ ] **Step 4: 修改 `AssistantShell.vue` script**

import 区改为：

```js
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth } from '../stores'
import UiIcon from './UiIcon.vue'
```

删除 `goHome` 函数：

```js
function goHome() {
  router.push('/home')
}
```

在 `const router = useRouter()` 之后添加：

```js
const { user, logout } = useAuth()
const displayName = computed(() => user.value?.realName || user.value?.username || '患者')
const initial = computed(() => displayName.value[0])

async function signOut() {
  await logout()
  router.replace('/login')
}
```

- [ ] **Step 5: 修改 `AssistantShell.vue` template**

侧栏顶部品牌按钮

```vue
          <button class="assistant-shell__brand" type="button" @click="goHome">
            <span class="assistant-shell__logo" aria-hidden="true"><UiIcon name="logo" :size="18" /></span>
            <span class="assistant-shell__brand-text">温润医院</span>
          </button>
```

改为纯展示：

```vue
          <div class="assistant-shell__brand">
            <span class="assistant-shell__logo" aria-hidden="true"><UiIcon name="logo" :size="18" /></span>
            <span class="assistant-shell__brand-text">温润医院</span>
          </div>
```

侧栏底部

```vue
        <div class="assistant-shell__sidebar-foot">
          <button class="assistant-shell__home" type="button" @click="goHome">
            <UiIcon name="arrowLeft" :size="16" />
            返回患者服务
          </button>
        </div>
```

改为

```vue
        <div class="assistant-shell__sidebar-foot">
          <nav class="assistant-shell__links" aria-label="患者服务">
            <RouterLink class="assistant-shell__link" to="/registration"><UiIcon name="calendar" :size="16" />预约挂号</RouterLink>
            <RouterLink class="assistant-shell__link" to="/user"><UiIcon name="user" :size="16" />个人中心</RouterLink>
          </nav>
          <div class="assistant-shell__account">
            <span class="assistant-shell__avatar" aria-hidden="true">{{ initial }}</span>
            <strong>{{ displayName }}</strong>
            <button class="assistant-shell__logout" type="button" aria-label="退出登录" title="退出登录" @click="signOut">
              <UiIcon name="logout" :size="16" />
            </button>
          </div>
        </div>
```

- [ ] **Step 6: 修改 `AssistantShell.vue` 样式**

`.assistant-shell__brand` 规则里删除 `border: 0; background: transparent; cursor: pointer; font: inherit;` 四行，并删除整个 `.assistant-shell__brand:hover { ... }` 块。

删除 `.assistant-shell__home` 与 `.assistant-shell__home:hover, .assistant-shell__home:focus-visible` 两个规则块，在原位置写入：

```css
.assistant-shell__sidebar-foot {
  padding: 8px 10px 12px;
  border-top: 1px solid #eef0f2;
}

.assistant-shell__links {
  display: grid;
  gap: 2px;
}

.assistant-shell__link {
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 40px;
  padding: 0 10px;
  border-radius: 10px;
  color: var(--color-text);
  font-size: 14px;
  text-decoration: none;
}

.assistant-shell__link svg {
  color: var(--color-brand-700);
}

.assistant-shell__link:hover,
.assistant-shell__link:focus-visible {
  background: rgba(16, 24, 32, .06);
}

.assistant-shell__account {
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 44px;
  margin-top: 6px;
  padding: 0 4px 0 10px;
}

.assistant-shell__avatar {
  width: 30px;
  height: 30px;
  display: grid;
  place-items: center;
  flex: 0 0 30px;
  border-radius: 9px;
  background: var(--color-brand-800);
  color: #fff;
  font-size: 13px;
  font-weight: 700;
}

.assistant-shell__account strong {
  min-width: 0;
  flex: 1;
  overflow: hidden;
  font-size: 14px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.assistant-shell__logout {
  display: grid;
  place-items: center;
  width: 34px;
  height: 34px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: var(--color-text-secondary);
  cursor: pointer;
}

.assistant-shell__logout:hover,
.assistant-shell__logout:focus-visible {
  background: rgba(16, 24, 32, .06);
  color: var(--color-danger);
}
```

（原 `.assistant-shell__sidebar-foot { padding: 8px 10px 14px; }` 被上面的新规则替换，删除旧的。）

在文件末尾 `@media (prefers-reduced-motion: reduce)` 之前追加移动端 Tabbar 留位：

```css
@media (max-width: 767px) {
  .assistant-shell {
    --tabbar-height: calc(68px + env(safe-area-inset-bottom));
    height: calc(100dvh - var(--tabbar-height));
    min-height: calc(100dvh - var(--tabbar-height));
  }

  .assistant-shell__sidebar,
  .assistant-shell__context,
  .assistant-shell__backdrop {
    bottom: var(--tabbar-height);
  }
}
```

- [ ] **Step 7: Lint + 测试**

Run: `cd frontend; npm run lint; npm test`
Expected: lint 无输出；`pass 39`, `fail 0`。

- [ ] **Step 8: 手动验证（dev server 已在跑，`npm run dev`）**

浏览器打开 `http://localhost:5173/assistant`（此时路由未切换，仍是助手页）：
- 无消息的会话显示欢迎区（问候、下次就诊、3 个 chip、今日可预约）；点击"帮我挂号"chip 直接发送消息并进入聊天流。
- 侧栏底部有"预约挂号 / 个人中心"和账号行；点击退出图标回到登录页。
- 缩到 < 768px：底部出现 Tabbar，输入框在 Tabbar 之上，不被遮挡。

- [ ] **Step 9: Commit**

```bash
git add frontend/src/views/Assistant.vue frontend/src/components/AssistantShell.vue
git commit -m "feat(home): 助手页接入欢迎空状态、移动端 Tabbar，侧栏底部改为业务导航"
```

---

### Task 5: 路由切换、导航精简、删除 `Home.vue`

**Files:**
- Modify: `frontend/src/router/index.js`
- Modify: `frontend/src/components/AppShell.vue:16-21`
- Modify: `frontend/src/components/MobileTabbar.vue`
- Modify: `frontend/src/styles/clinic-theme.css:267-279`
- Delete: `frontend/src/views/Home.vue`
- Test: `frontend/test/shell.test.js`

**Interfaces:**
- Consumes: Task 1 的 `assistantRedirect`；Task 4 完成后的 `Assistant.vue`。

- [ ] **Step 1: 写失败测试**

`frontend/test/shell.test.js` 全文替换为：

```js
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const read = (path) => readFileSync(join(here, path), 'utf8')
const source = read('../src/components/AppShell.vue')
const tabbar = read('../src/components/MobileTabbar.vue')
const router = read('../src/router/index.js')

test('sidebar brand logo is not targeted by generic brand span rules', () => {
  assert.match(source, /class="app-shell__logo"/)
  assert.match(source, /class="app-shell__brand-text"/)
  assert.doesNotMatch(source, /\.app-shell__brand span\b/)
  assert.match(source, /\.app-shell__logo\s*\{[^}]*display:\s*grid/)
})

test('patient navigation no longer exposes a separate assistant entry', () => {
  assert.doesNotMatch(source, /to: '\/assistant'/)
  assert.equal((source.match(/\{ to: '/g) || []).length, 3)
  assert.doesNotMatch(tabbar, /\/assistant|featured/)
  assert.equal((tabbar.match(/\{ to: '/g) || []).length, 3)
  assert.match(tabbar, /to: '\/home', icon: 'ai', label: '首页'/)
})

test('home route renders the assistant and the legacy assistant path redirects', () => {
  assert.match(router, /path: '\/home', component: \(\) => import\('\.\.\/views\/Assistant\.vue'\)/)
  assert.match(router, /path: '\/assistant', redirect: assistantRedirect/)
  assert.doesNotMatch(router, /Home\.vue/)
})
```

- [ ] **Step 2: 运行确认失败**

Run: `cd frontend; npm test`
Expected: 新增 2 个测试失败（`patient navigation ...`、`home route ...`），其余通过。

- [ ] **Step 3: 修改路由**

`frontend/src/router/index.js` 全文替换为：

```js
import { createRouter, createWebHistory } from 'vue-router'
import { useAuth } from '../stores'
import { homePath } from '../utils/portal'
import { assistantRedirect, isPatientPortal } from '../features/experience/mode'

const routes = [
  { path: '/', redirect: '/login' },
  { path: '/login', component: () => import('../views/Login.vue'), meta: { guest: true } },
  { path: '/mode-select', redirect: '/home', meta: { patient: true } },
  { path: '/home', component: () => import('../views/Assistant.vue'), meta: { patient: true } },
  { path: '/assistant', redirect: assistantRedirect },
  { path: '/user', component: () => import('../views/User.vue'), meta: { patient: true } },
  { path: '/registration', component: () => import('../views/Registration.vue'), meta: { patient: true } },
  { path: '/registration/:id', component: () => import('../views/RegistrationDetail.vue'), meta: { patient: true } },
  { path: '/:pathMatch(.*)*', redirect: '/login' },
]

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach((to) => {
  if (import.meta.env.DEV && to.path === '/home' && to.query.preview === '1') return true
  const { user, isAuthenticated } = useAuth()
  if (to.meta.guest && isAuthenticated.value) return homePath()
  if (!to.meta.guest && !isAuthenticated.value) return '/login'
  if (to.meta.patient && !isPatientPortal(user.value)) return '/login'
  return true
})

export default router
```

- [ ] **Step 4: 精简 `AppShell.vue` 导航**

```js
const nav = [
  { to: '/home', icon: 'home', label: '首页' },
  { to: '/assistant', icon: 'ai', label: 'AI 健康助手' },
  { to: '/registration', icon: 'calendar', label: '预约挂号' },
  { to: '/user', icon: 'user', label: '个人中心' },
]
```

改为

```js
const nav = [
  { to: '/home', icon: 'home', label: '首页' },
  { to: '/registration', icon: 'calendar', label: '预约挂号' },
  { to: '/user', icon: 'user', label: '个人中心' },
]
```

- [ ] **Step 5: 精简 `MobileTabbar.vue`**

```js
const tabs = [
  { to: '/home', icon: 'home', label: '首页' },
  { to: '/registration', icon: 'calendar', label: '挂号' },
  { to: '/assistant', icon: 'ai', label: 'AI 助手', featured: true },
  { to: '/user', icon: 'user', label: '我的' },
]
```

改为

```js
const tabs = [
  { to: '/home', icon: 'ai', label: '首页' },
  { to: '/registration', icon: 'calendar', label: '挂号' },
  { to: '/user', icon: 'user', label: '个人中心' },
]
```

模板中 `:class` 去掉 featured：

```vue
      class="mobile-tabbar__item" :class="{ 'mobile-tabbar__item--active': active(tab.to) }" :aria-current="active(tab.to) ? 'page' : undefined">
```

- [ ] **Step 6: 删除 featured 样式**

`frontend/src/styles/clinic-theme.css` 删除以下规则：

```css
.mobile-tabbar__item--featured { position: relative; padding-top: 3px; }
.mobile-tabbar__item--featured svg {
  width: 47px;
  height: 47px;
  margin-top: -20px;
  padding: 11px;
  border: 4px solid #fff;
  border-radius: 50%;
  background: var(--color-brand-700);
  color: #fff;
  box-shadow: 0 8px 20px rgba(15, 143, 130, .24);
}
.mobile-tabbar__item--featured.mobile-tabbar__item--active svg { background: var(--color-brand-900); }
```

- [ ] **Step 7: 删除 `Home.vue`**

```bash
git rm frontend/src/views/Home.vue
```

- [ ] **Step 8: 测试 + Lint + Build**

Run: `cd frontend; npm test; npm run lint; npm run build`
Expected: `pass 41`, `fail 0`；lint 无输出；build 成功输出 `dist/`，无 `Home.vue` 相关报错。

- [ ] **Step 9: 手动验证**

- `http://localhost:5173/home`：直接是助手页；无消息时显示欢迎区。
- `http://localhost:5173/assistant?prompt=你好`：地址栏变为 `/home`，消息"你好"自动发出。
- PC 侧栏（挂号页）主导航只剩首页 / 预约挂号 / 个人中心；点"首页"回到助手页并恢复上次会话。
- < 768px：Tabbar 3 项，首页项用 AI 图标且无中间突出样式；在挂号页点"首页"回到助手页。
- 登录后自动进入 `/home`。

- [ ] **Step 10: Commit**

```bash
git add frontend/src/router/index.js frontend/src/components/AppShell.vue frontend/src/components/MobileTabbar.vue frontend/src/styles/clinic-theme.css frontend/test/shell.test.js
git commit -m "feat(home): 首页与 AI 健康助手合并，导航减为 3 项，移除 Home.vue"
```

---

## Self-Review

- **Spec coverage**：§2 路由 → Task 1、5；§3 欢迎组件（内容、数据、事件、样式）→ Task 2、3、4；§4.1 AssistantShell → Task 4；§4.2 Assistant.vue → Task 4；§4.3 AppShell、§4.4 MobileTabbar → Task 5；§5 删除 → Task 4（goHome/home 按钮）、Task 5（Home.vue、featured CSS）；§7 测试 → Task 1、2、5 与各任务的 lint/build/手动验证。无遗漏。
- **Placeholder scan**：所有代码步骤含完整代码；命令含预期输出。
- **Type consistency**：`assistantRedirect(to)` 在 Task 1 定义、Task 5 引用；`nextAppointment` / `bookableToday(schedules, limit, now)` 在 Task 2 定义、Task 3 使用（`bookableToday(list)` 使用默认参数）；`AssistantWelcome` props `appointments` / `appointmentsError`、事件 `prompt` 在 Task 3 定义、Task 4 以 `:appointments` / `:appointments-error` / `@prompt` 使用，一致。
