import test from 'node:test'
import assert from 'node:assert/strict'

import {
  appendProgressStep,
  completeProgressSteps,
  progressStepLabel,
  progressSummary,
} from '../src/features/assistant/progress.js'

test('assistant progress keeps ordered unique server statuses', () => {
  let steps = appendProgressStep([], '正在分析您的问题…')
  steps = appendProgressStep(steps, '正在检索相关资料…')
  steps = appendProgressStep(steps, '正在检索相关资料…')
  assert.deepEqual(steps, ['正在分析您的问题…', '正在检索相关资料…'])
})

test('assistant progress adds a visible completion step', () => {
  const steps = completeProgressSteps(['正在整理答案…'])
  assert.deepEqual(steps, ['正在整理答案…', '回答已生成'])
  assert.equal(progressSummary('completed', steps), '已完成处理')
})

test('assistant progress labels are concise for the timeline', () => {
  assert.equal(progressStepLabel('正在拆解您的请求…'), '拆解您的请求')
  assert.equal(progressSummary('error', []), '处理未完成')
})
