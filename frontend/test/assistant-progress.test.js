import test from 'node:test'
import assert from 'node:assert/strict'

import {
  appendProgressStep,
  completeProgressSteps,
  progressStepLabel,
  progressSummary,
  progressRows,
  stepElapsedMs,
  interruptProgressSteps,
} from '../src/features/assistant/progress.js'

test('stopped steps freeze elapsed time and preserve finished steps', () => {
  const steps = [{ id: 'a', status: 'completed', elapsedMs: 10 }, { id: 'b', status: 'running', receivedAt: 1000, elapsedMs: 0 }]
  const stopped = interruptProgressSteps(steps, 'stopped', 6000)
  assert.equal(stopped[0], steps[0])
  assert.equal(stopped[1].status, 'failed')
  assert.equal(stepElapsedMs(stopped[1], 9000), 5000)
  assert.equal(interruptProgressSteps(steps, 'confirming', 6000)[1].status, 'waiting')
})

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

test('parallel operations remain running until their own completion event', () => {
  let steps = appendProgressStep([], { id: 'knowledge', label: '整理健康建议', status: 'running' })
  steps = appendProgressStep(steps, { id: 'tools', label: '查询号源', status: 'running' })
  const received = steps[0].receivedAt
  steps = appendProgressStep(steps, { id: 'tools', label: '查询号源', status: 'completed', elapsedMs: 800 })
  assert.equal(steps.length, 2)
  assert.equal(steps[0].status, 'running')
  assert.equal(steps[0].receivedAt, received)
  assert.equal(progressSummary('streaming', steps), '正在整理健康建议…')
  assert.equal(stepElapsedMs(steps[0], received + 1500), 1500)
  assert.equal(stepElapsedMs(steps[1], received + 1500), 800)
})

test('failure and confirmation do not pretend unfinished steps succeeded', () => {
  const steps = [{ id: 'tools', label: '查询号源', status: 'running' }]
  assert.equal(progressRows(steps, 'error')[0].status, 'failed')
  assert.equal(progressRows(steps, 'confirming')[0].status, 'waiting')
  const failed = appendProgressStep([], { id: 'tools', label: '查询号源', status: 'failed', elapsedMs: 2000 })
  assert.equal(completeProgressSteps(failed)[0].status, 'failed')
  assert.equal(progressSummary('completed', failed), '回答已生成，部分查询未完成')
})

test('structured progress retains a complete multi-stage history and rejects malformed states', () => {
  let steps = []
  for (let i = 0; i < 12; i++) steps = appendProgressStep(steps, { id: String(i), label: '操作', status: 'completed' })
  assert.equal(steps.length, 12)
  assert.deepEqual(appendProgressStep(steps, { id: 'bad', label: '操作', status: 'unknown' }), steps)
})
