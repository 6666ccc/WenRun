# 健康数据分项记录弹窗 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 档案健康数据每张可填卡只打开该项记录弹窗，不再一次改整组体型或生命体征。

**Architecture:** 在 `healthProfile.js` 增加 8 个指标编辑配置。卡片 `emit` 对应 id。`PatientArchive` 按配置渲染字段，保存仍走整份 `createHealthProfile` / `updateHealthProfile`，未改字段原样带回。

**Tech Stack:** Vue 3 `<script setup>`、`node --test`、现有 clinic token。

**Spec:** `docs/superpowers/specs/2026-09-19-archive-metric-editors-design.md`

## Global Constraints

- 只改 `frontend/`。不改后端、不加接口。
- 命令在 `frontend/`：`npm test`、`npm run lint`、`npm run build`。
- 可记录 id：`weight` | `height` | `bp` | `glucose` | `hr` | `spo2` | `rr` | `temp`。不再使用 `body`、`vitals`。
- 去掉分区「记录数据 ›」。腰围 / WHtR 仍套壳。BMI 不编辑。
- 不提交 git（除非用户要求）。

---

## File Structure

| 文件 | 操作 | 职责 |
| --- | --- | --- |
| `frontend/src/utils/healthProfile.js` | 修改 | 导出 `METRIC_EDITORS`、`metricEditor(id)`、`isMetricEditor(id)` |
| `frontend/test/health-profile.test.js` | 修改 | 配置覆盖 8 个 id 与字段 |
| `frontend/src/components/archive/ArchiveHealthData.vue` | 修改 | 每张卡 emit 分项 id，删除「记录数据 ›」 |
| `frontend/src/views/PatientArchive.vue` | 修改 | 按配置渲染分项弹窗 |
| `frontend/test/health-trend.test.js` | 修改 | 入口与字段断言改到新约定 |
| `frontend/test/archive.test.js` | 修改 | 断言不再出现整组 `body`/`vitals` 表单 |

---

### Task 1: 指标编辑配置

**Files:**
- Modify: `frontend/src/utils/healthProfile.js`
- Test: `frontend/test/health-profile.test.js`

**Interfaces:**
- Consumes: 现有 `GLUCOSE_TYPE_MAP`（血糖选项文案）
- Produces:
  - `METRIC_EDITORS`: `{ [id: string]: { title: string, fields: Array<{ key, label, type, step?, min?, max?, options? }> } }`
  - `metricEditor(id: string): object | null`
  - `isMetricEditor(id: string): boolean`
  - ids：`weight` `height` `bp` `glucose` `hr` `spo2` `rr` `temp`
  - `measuredAt` 不进各 editor 的 `fields`，由弹窗模板统一渲染

- [x] **Step 1: Write the failing test**

在 `frontend/test/health-profile.test.js` 增加 import 与测试：

```js
import {
  METRIC_EDITORS,
  isMetricEditor,
  metricEditor,
} from '../src/utils/healthProfile.js'

test('metric editors cover eight recordable ids and not BMI', () => {
  assert.deepEqual(Object.keys(METRIC_EDITORS), ['weight', 'height', 'bp', 'glucose', 'hr', 'spo2', 'rr', 'temp'])
  assert.equal(isMetricEditor('bp'), true)
  assert.equal(isMetricEditor('vitals'), false)
  assert.equal(isMetricEditor('body'), false)
  assert.equal(isMetricEditor('bmi'), false)
  assert.equal(metricEditor('unknown'), null)
})

test('metric editor fields match the focused dialog spec', () => {
  const keys = (id) => metricEditor(id).fields.map((field) => field.key)
  assert.equal(metricEditor('weight').title, '记录体重')
  assert.deepEqual(keys('weight'), ['weightKg'])
  assert.deepEqual(keys('height'), ['heightCm'])
  assert.deepEqual(keys('bp'), ['systolicMmhg', 'diastolicMmhg'])
  assert.deepEqual(keys('glucose'), ['glucoseMmol', 'glucoseType'])
  assert.deepEqual(keys('hr'), ['heartRateBpm'])
  assert.deepEqual(keys('spo2'), ['spo2Pct'])
  assert.deepEqual(keys('rr'), ['respiratoryRateBpm'])
  assert.deepEqual(keys('temp'), ['temperatureC'])
  assert.equal(metricEditor('glucose').fields[1].type, 'select')
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- test/health-profile.test.js`（在 `frontend/`）

Expected: FAIL，`METRIC_EDITORS` 未导出。

- [ ] **Step 3: Write minimal implementation**

在 `frontend/src/utils/healthProfile.js` 末尾追加：

```js
export const METRIC_EDITORS = {
  weight: {
    title: '记录体重',
    fields: [{ key: 'weightKg', label: '体重 kg', type: 'number', step: '0.1', min: 10, max: 300 }],
  },
  height: {
    title: '记录身高',
    fields: [{ key: 'heightCm', label: '身高 cm', type: 'number', step: '0.1', min: 50, max: 250 }],
  },
  bp: {
    title: '记录血压',
    fields: [
      { key: 'systolicMmhg', label: '收缩压 mmHg', type: 'number', min: 60, max: 250 },
      { key: 'diastolicMmhg', label: '舒张压 mmHg', type: 'number', min: 40, max: 180 },
    ],
  },
  glucose: {
    title: '记录血糖',
    fields: [
      { key: 'glucoseMmol', label: '血糖 mmol/L', type: 'number', step: '0.1', min: 1, max: 40 },
      {
        key: 'glucoseType',
        label: '血糖类型',
        type: 'select',
        options: [
          { value: '', label: '未填写' },
          { value: 'fasting', label: '空腹' },
          { value: 'random', label: '随机' },
          { value: 'postprandial', label: '餐后' },
        ],
      },
    ],
  },
  hr: {
    title: '记录心率',
    fields: [{ key: 'heartRateBpm', label: '心率 次/分', type: 'number', min: 30, max: 220 }],
  },
  spo2: {
    title: '记录血氧',
    fields: [{ key: 'spo2Pct', label: '血氧 %', type: 'number', min: 50, max: 100 }],
  },
  rr: {
    title: '记录呼吸',
    fields: [{ key: 'respiratoryRateBpm', label: '呼吸 次/分', type: 'number', min: 8, max: 40 }],
  },
  temp: {
    title: '记录体温',
    fields: [{ key: 'temperatureC', label: '体温 ℃', type: 'number', step: '0.1', min: 35, max: 42 }],
  },
}

export function metricEditor(id) {
  return METRIC_EDITORS[id] || null
}

export function isMetricEditor(id) {
  return Boolean(METRIC_EDITORS[id])
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- test/health-profile.test.js`

Expected: PASS

- [ ] **Step 5: Commit**

跳过。全局约束：不提交 git。

---

### Task 2: 卡片按项 emit

**Files:**
- Modify: `frontend/src/components/archive/ArchiveHealthData.vue`
- Test: `frontend/test/health-trend.test.js`

**Interfaces:**
- Consumes: Task 1 的 id 字符串
- Produces: `@record` 值为 `weight` / `height` / `bp` / `glucose` / `hr` / `spo2` / `rr` / `temp`

- [x] **Step 1: Write the failing test**

替换 `frontend/test/health-trend.test.js` 中 `archive vitals cards...` 测试，并新增入口断言：

```js
test('archive metric cards emit one editor id each and drop group record links', () => {
  const healthData = readFileSync(join(here, '../src/components/archive/ArchiveHealthData.vue'), 'utf8')
  assert.doesNotMatch(healthData, /记录数据/)
  assert.doesNotMatch(healthData, /emit\('record', 'body'\)/)
  assert.doesNotMatch(healthData, /emit\('record', 'vitals'\)/)
  assert.match(healthData, /emit\('record', 'weight'\)/)
  assert.match(healthData, /emit\('record', 'height'\)/)
  assert.match(healthData, /emit\('record', 'bp'\)/)
  assert.match(healthData, /emit\('record', 'glucose'\)/)
  assert.match(healthData, /emit\('record', 'hr'\)/)
  assert.match(healthData, /emit\('record', 'spo2'\)/)
  assert.match(healthData, /emit\('record', 'rr'\)/)
  assert.match(healthData, /emit\('record', 'temp'\)/)
  assert.match(healthData, /health\?\.spo2Pct/)
  assert.match(healthData, /health\?\.respiratoryRateBpm/)
  assert.match(healthData, /health\?\.temperatureC/)
  assert.doesNotMatch(healthData, /emit\('unavailable', '血氧'\)/)
})
```

删除对 `PatientArchive.vue` 里 `healthForm.spo2Pct` 字面量的旧断言（该测试整段替换即可）。

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- test/health-trend.test.js`

Expected: FAIL，仍在 emit `body`/`vitals`，仍有「记录数据」。

- [ ] **Step 3: Write minimal implementation**

`ArchiveHealthData.vue`：

1. 删除两个 header 里的 `<button class="archive-link" ...>记录数据 ›</button>`。
2. 替换 emit：
   - 体重 `emit('record', 'weight')`
   - 身高 `emit('record', 'height')`
   - 血压 `emit('record', 'bp')`
   - 血糖 `emit('record', 'glucose')`
   - 心率 `emit('record', 'hr')`
   - 血氧 `emit('record', 'spo2')`
   - 呼吸 `emit('record', 'rr')`
   - 体温 `emit('record', 'temp')`
3. 腰围 / WHtR / 就医资料套壳不变。

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- test/health-trend.test.js`

Expected: PASS

- [ ] **Step 5: Commit**

跳过。

---

### Task 3: 分项弹窗

**Files:**
- Modify: `frontend/src/views/PatientArchive.vue`
- Test: `frontend/test/archive.test.js`

**Interfaces:**
- Consumes: `metricEditor`、`isMetricEditor`（Task 1）
- Produces: `editor` 为指标 id 时只渲染该配置字段 + 测量时间；保存仍 `saveHealth()`

- [x] **Step 1: Write the failing test**

在 `frontend/test/archive.test.js` 增加：

```js
test('archive page renders metric editors from config instead of grouped body/vitals forms', () => {
  const page = read('../src/views/PatientArchive.vue')
  assert.match(page, /metricEditor/)
  assert.match(page, /isMetricEditor/)
  assert.doesNotMatch(page, /editor === 'body'/)
  assert.doesNotMatch(page, /editor === 'vitals'/)
  assert.doesNotMatch(page, /记录生命体征/)
  assert.match(page, /healthForm\.measuredAt/)
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- test/archive.test.js`

Expected: FAIL，页面仍有 `editor === 'vitals'`。

- [ ] **Step 3: Write minimal implementation**

`PatientArchive.vue`：

1. import：

```js
import { emptyHealthForm, fillHealthForm, isMetricEditor, metricEditor, toHealthPayload } from '../utils/healthProfile'
```

2. 替换 `editorTitle`：

```js
const editorTitle = computed(() => {
  if (editor.value === 'basic') return '基本资料'
  if (editor.value === 'history') return '健康信息'
  return metricEditor(editor.value)?.title || '记录数据'
})

const metricFields = computed(() => metricEditor(editor.value)?.fields || [])
```

3. `watch(editor)`：

```js
watch(editor, (value) => { if (isMetricEditor(value)) fillHealth(health.value) })
```

4. 模板：删除 `editor === 'body'` / `v-else` 整组字段。指标弹窗改为：

```vue
<form v-else-if="isMetricEditor(editor)" @submit.prevent="saveHealth()">
  <h3>{{ editorTitle }}</h3>
  <label v-for="field in metricFields" :key="field.key">
    {{ field.label }}
    <select v-if="field.type === 'select'" v-model="healthForm[field.key]" class="input">
      <option v-for="option in field.options" :key="option.value" :value="option.value">{{ option.label }}</option>
    </select>
    <input
      v-else
      v-model="healthForm[field.key]"
      class="input"
      :type="field.type"
      :step="field.step"
      :min="field.min"
      :max="field.max"
    >
  </label>
  <label>测量时间<input v-model="healthForm.measuredAt" class="input" type="datetime-local"></label>
  <div class="archive-dialog__actions">
    <button class="btn btn--ghost" type="button" @click="closeEditor">取消</button>
    <button class="btn btn--primary" type="submit" :disabled="healthSaving">{{ healthSaving ? '保存中…' : '保存' }}</button>
  </div>
</form>
```

5. `saveHealth` 逻辑不变（整份 payload、失败不关窗）。

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- test/archive.test.js`

Expected: PASS

- [ ] **Step 5: Commit**

跳过。

---

### Task 4: 全量验证

**Files:** 无新文件

- [ ] **Step 1: Run frontend tests**

Run: `npm test`（`frontend/`）

Expected: 全部 PASS。

- [ ] **Step 2: Run lint**

Run: `npm run lint`

Expected: 无新增 error。

- [ ] **Step 3: Run build**

Run: `npm run build`

Expected: 成功。

- [ ] **Step 4: Browser check**

打开 `/archive`：点血压「+」只见收缩压/舒张压/测量时间；点体重只见体重；header 无「记录数据 ›」；保存后该卡更新、其它卡不变。移动端宽度再看一次弹窗。

- [ ] **Step 5: Commit**

跳过。
