import test from 'node:test'
import assert from 'node:assert/strict'

import { consumeChatEvents, normalizeChatEvent } from '../src/api/modules/ai.js'

test('normalizeChatEvent returns the event unchanged', () => {
  const event = {
    type: 'done',
    conversationId: 'conversation-1',
    reply: 'hello',
  }

  assert.deepEqual(normalizeChatEvent(event), event)
})

test('done event aggregates reply intent and sources', async () => {
  const result = await consumeChatEvents([
    { type: 'status', content: '正在检索相关资料…' },
    { type: 'token', content: '外' },
    { type: 'token', content: '科' },
    { type: 'citation', excerpt: '门诊楼三层' },
    { type: 'done', reply: '外科在门诊楼三层', intent: 'hospital', sources: [{ id: 'S1' }] },
  ])
  assert.equal(result.status, 'completed')
  assert.equal(result.reply, '外科在门诊楼三层')
  assert.equal(result.intent, 'hospital')
  assert.equal(result.sources[0].id, 'S1')
})

test('status and citations never become assistant reply text', async () => {
  const result = await consumeChatEvents([
    { type: 'status', content: '正在检索相关资料…' },
    { type: 'citation', sources: [{ id: 'S1', title: '公开资料' }] },
    { type: 'token', content: '最终答案' },
    { type: 'done', reply: '最终答案', sources: [{ id: 'S1', title: '公开资料' }] },
  ])

  assert.equal(result.reply, '最终答案')
  assert.deepEqual(result.sources, [{ id: 'S1', title: '公开资料' }])
})

test('events after done are ignored', async () => {
  const result = await consumeChatEvents([
    { type: 'token', content: '已完成' },
    { type: 'done', reply: '已完成', sources: [] },
    { type: 'token', content: '不应追加的内部内容' },
  ])

  assert.equal(result.reply, '已完成')
  assert.doesNotMatch(result.reply, /内部内容/)
})
