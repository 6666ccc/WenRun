import test from 'node:test'
import assert from 'node:assert/strict'

import { normalizeChatEvent, taskFromChatEvent } from '../src/api/modules/ai.js'

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
