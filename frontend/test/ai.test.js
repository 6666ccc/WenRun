import test from 'node:test'
import assert from 'node:assert/strict'

import { consumeChatEvents, normalizeChatEvent, taskFromChatEvent } from '../src/api/modules/ai.js'
import { buildResumePayload } from '../src/features/assistant/interrupt.js'
import { AI_REGISTRATION_PROMPT } from '../src/features/assistant/registration.js'

test('normalizeChatEvent returns the event unchanged', () => {
  const event = {
    type: 'done',
    conversationId: 'conversation-1',
    reply: 'hello',
  }

  assert.deepEqual(normalizeChatEvent(event), event)
})

test('taskFromChatEvent ignores unknown and clinician-only events', () => {
  assert.equal(taskFromChatEvent({ type: 'tool', task: { type: 'prescription' } }), null)
  assert.deepEqual(taskFromChatEvent({ type: 'tool', task: { type: 'payment', chargeId: 8 } }), { type: 'payment', chargeId: 8 })
})

test('interrupt is a successful terminal stream event', async () => {
  const seen = []
  const result = await consumeChatEvents([
    { type: 'status', content: '查询号源' },
    { type: 'interrupt', interrupt: { interruptId: 'i-1', action: 'registration:create' } },
  ], { onInterrupt: (value) => seen.push(value) })
  assert.equal(result.status, 'pending')
  assert.equal(seen[0].interruptId, 'i-1')
})

test('buildResumePayload keeps the interrupt identity', () => {
  assert.deepEqual(buildResumePayload('c-1', 'i-1', true), {
    conversationId: 'c-1',
    interruptId: 'i-1',
    approved: true,
  })
})

test('done event aggregates reply intent and sources', async () => {
  const result = await consumeChatEvents([
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

test('AI registration starts as a chat prompt instead of a patient API write', () => {
  assert.equal(AI_REGISTRATION_PROMPT, '帮我预约挂号')
})
