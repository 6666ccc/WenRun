# 患者个人档案独立页 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 点击「个人档案」进入独立全页 `/archive`（对齐产品图）；`/home` 聊天首页保持不变。

**Architecture:** `/archive` 走 `AppShell` + 新档案组件，不进 `PatientWorkspace` 抽屉。`/user` 重定向到 `/archive`。有库字段接现有 patient / health-profile / registration 接口；无库模块用 `ArchiveUnavailable` 标明「数据库还未设计」。

**Tech Stack:** Vue 3 `<script setup>`、vue-router 4、Vite、`node --test`、ESLint。

**Spec:** `docs/superpowers/specs/2026-09-19-patient-archive-design.md`

## Global Constraints

- 只改 `frontend/`。不改后端、不加表。不改 `/home` 聊天欢迎态。
- 命令在 `frontend/`：`npm test`、`npm run lint`、`npm run build`。
- 套壳文案固定「数据库还未设计」。
- 导航文案改为「个人档案」，目标 `/archive`。
- 不提交 git（除非用户要求）。

---

## File Structure

| 文件 | 操作 | 职责 |
| --- | --- | --- |
| `frontend/src/features/archive/tabs.js` | 新建 | `archiveTabFromQuery`、`calcAge`、`maskIdCard` |
| `frontend/src/features/experience/mode.js` | 修改 | `userArchiveRedirect()` |
| `frontend/src/features/experience/workspace.js` | 修改 | 删除 `/user` 抽屉映射 |
| `frontend/src/router/index.js` | 修改 | `/archive` 新页，`/user` redirect |
| `frontend/src/components/AppShell.vue` 等导航 | 修改 | 指向 `/archive` |
| `frontend/src/views/PatientArchive.vue` | 新建 | 档案页容器 |
| `frontend/src/components/archive/*.vue` | 新建 | 侧栏、各 Tab、套壳 |
| `frontend/src/views/User.vue`、`UserProfile.vue` | 删除 | 旧个人中心 |
| `frontend/test/experience.test.js`、`shell.test.js`、`archive.test.js` | 修改/新建 | 路由与纯函数测试 |

首页相关：`Assistant.vue` 仅改 `openTask` 的 records 目标；不改欢迎空状态与聊天布局。
