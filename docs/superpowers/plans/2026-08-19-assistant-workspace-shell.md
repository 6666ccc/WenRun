# 健康助手独立 AI 工作区 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 进入 `/assistant` 后展示全屏 AI 专注工作区（会话栏 + 聊天 + 就诊资料），随时 `router.push('/home')` 回到患者服务；挂号/缴费仍在现有业务页完成。

**Architecture:** 仅 `Assistant.vue` 改包 `AssistantShell`；其它患者页继续用 `AppShell`。壳层负责顶栏、三栏、右栏折叠与窄屏抽屉；会话与流式仍由 `useAssistant` 提供。

**Tech Stack:** Vue 3 + Vue Router + 现有薄荷绿 CSS 变量 + Node test runner。

## Global Constraints

- 不修改 Java/Python AI 服务、流式事件、中断 payload、鉴权、会话存储键 `wenrun_ai_sessions` 与按用户隔离策略。
- 不复制挂号/缴费表单；确认后仍跳转现有业务页。
- 返回目标一律 `router.push('/home')`。
- 本轮不做：会话重命名、搜消息正文、模型选择器、后端会话隔离、把选壳提升到 `App.vue`。
- 右栏折叠只活在当前页，刷新后桌面默认展开。

See the Cursor plan `助手工作区壳层` and spec `docs/superpowers/specs/2026-08-19-assistant-workspace-shell-design.md`.
