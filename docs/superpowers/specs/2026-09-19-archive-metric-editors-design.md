# 健康数据分项记录弹窗 — 设计文档

日期：2026-09-19
范围：`frontend/`。不改后端、不加接口、不改趋势写入逻辑。

## 1. 背景与目标

现状：体型分区的「记录数据 ›」和每张卡的「+」都打开同一份身高+体重表单；生命体征分区的入口都打开同一份血压/血糖/心率/血氧/呼吸/体温表单。一次弹出改全部字段，和卡片上「记录血压」「记录血糖」的语义不符。

目标：每张可填卡只记录这一项。保存仍走现有健康档案整份写入，未改字段原样带回。

已确认的取舍：

- 粒度 A：每张卡独立弹窗。血压仍是收缩压+舒张压；血糖仍带类型。
- 体型也拆：身高、体重各自独立。BMI 只展示，不编辑。
- 去掉分区标题「记录数据 ›」，只留卡上的「+」。
- 写入方案 1：前端拆弹窗，接口仍是 `createHealthProfile` / `updateHealthProfile`。

## 2. 入口

`ArchiveHealthData.vue`：

- 删除体型、生命体征 header 里的「记录数据 ›」。
- 体重 / 身高 / 血压 / 血糖 / 心率 / 血氧 / 呼吸 / 体温的「+」分别 `emit('record', id)`。
- 腰围、WHtR 仍 `emit('unavailable', …)`，文案「数据库还未设计」。
- BMI 卡没有「+」。

`id` 取值：`weight` | `height` | `bp` | `glucose` | `hr` | `spo2` | `rr` | `temp`。不再使用 `body`、`vitals`。

这些 id 只存在于组件状态，不进路由 query。`/archive?tab=basic|history` 的基本资料 / 健康信息弹窗不变。

## 3. 弹窗

`PatientArchive.vue` 仍用现有 overlay。`editor` 为上表 id 时，标题和字段由配置驱动：

| id | 标题 | 可见字段 |
| --- | --- | --- |
| `weight` | 记录体重 | `weightKg`、`measuredAt` |
| `height` | 记录身高 | `heightCm`、`measuredAt` |
| `bp` | 记录血压 | `systolicMmhg`、`diastolicMmhg`、`measuredAt` |
| `glucose` | 记录血糖 | `glucoseMmol`、`glucoseType`、`measuredAt` |
| `hr` | 记录心率 | `heartRateBpm`、`measuredAt` |
| `spo2` | 记录血氧 | `spo2Pct`、`measuredAt` |
| `rr` | 记录呼吸 | `respiratoryRateBpm`、`measuredAt` |
| `temp` | 记录体温 | `temperatureC`、`measuredAt` |

配置放在 `utils/healthProfile.js`（标题、字段、input 约束），页面按配置渲染，避免再堆一组 `editor === 'vitals'` 分支。

打开时用当前 `health` 填满整份 `healthForm`。已有值带入该项；测量时间有则带入，无则保存时回落到当前时间（沿用现有 `saveHealth`）。取消关闭，不请求。

基本资料、健康信息仍走 `ArchiveBasicInfo` / `ArchiveHealthInfo`，不受本次影响。

## 4. 数据流

1. 打开弹窗：`fillHealth(health.value)`，整份表单对齐当前档案。
2. 用户只改可见字段。
3. 保存：`toHealthPayload(healthForm)` 仍提交完整档案。未改字段保持打开时的值。
4. 已有档案走 `updateHealthProfile`，没有则 `createHealthProfile`。
5. 成功后刷新 `health`、回填表单、关弹窗、提示「健康档案已保存」。趋势图继续用现有 `refreshKey`（`health.updateTime` 或 `measuredAt`）重拉。

后端 `syncMetricRecords` 已按数值变化写趋势：只改一项时，只有该项会多一条记录。本次不改后端。

不调用 `POST /api/health/metrics`。清空该项可见数值时，该项写成 `null`，其它指标不动。

## 5. 错误处理

- 保存失败：弹窗不关，`message` 显示「健康档案保存失败」（或接口返回文案）。
- 健康档案加载失败：现有 `healthError` 条不变；仍允许打开弹窗尝试创建/更新。
- 未绑定 `patientId`：整页空态，没有卡可点。
- 套壳卡不进编辑态。

## 6. 测试

- `test/health-profile.test.js`：配置覆盖 8 个 id；血压字段含收缩压和舒张压；BMI 不在可记录 id 里；身高/体重/血氧/呼吸/体温字段名齐全。
- `test/archive.test.js` 或 `health-trend.test.js`：`ArchiveHealthData.vue` 不再 `emit('record', 'body'|'vitals')`，不再出现「记录数据 ›」；各可填卡 `emit` 对应 id。`PatientArchive.vue` 不再出现 `editor === 'body'` / `editor === 'vitals'` 整组表单，改为按配置渲染。
- 现有 `health-trend.test.js` 里对 `healthForm.spo2Pct` 等页面字面量的断言，改到配置所在文件（`utils/healthProfile.js`），避免实现用 `v-for` 后误失败。
- 运行 `frontend` 下 `npm test`；有 lint / build 一并跑。

## 7. 不在范围内

- 后端、数据库、新接口。
- 改用 `POST /api/health/metrics` 做真·单条写入。
- 腰围、WHtR、就医资料、运动睡眠。
- 基本资料 / 健康信息弹窗改版。
- 把记录弹窗抽成独立 Vue 组件。
