import test from 'node:test'
import assert from 'node:assert/strict'

import { MODE_AGENT, MODE_CLASSIC, MODE_STORAGE_KEY, normalizeMode, patientHomePath, isPatientPortal, readMode, writeMode } from '../src/features/experience/mode.js'
import { filterSessionsByTitle, normalizeSessions, shouldRemoveLocalSessionAfterDeleteError } from '../src/features/assistant/session.js'
import { toTask } from '../src/features/assistant/task.js'

test('normalizeMode only accepts the two patient experiences', () => {
  assert.equal(normalizeMode('agent'), MODE_AGENT)
  assert.equal(normalizeMode('classic'), MODE_CLASSIC)
  assert.equal(normalizeMode('doctor'), MODE_AGENT)
})

test('normalizeSessions recovers a safe default after corrupt storage', () => {
  assert.deepEqual(normalizeSessions('{broken json'), [{ id: 'default', title: '新的问诊', messages: [] }])
})

test('normalizeSessions preserves request identity and normalizes message status', () => {
  const sessions = normalizeSessions([{
    id: 'conversation-1',
    title: '测试',
    messages: [
      { id: 'user-1', role: 'user', content: '你好', meta: { requestId: 'request-1', status: 'pending' } },
      { id: 'legacy-1', role: 'assistant', content: '旧回复', meta: { intent: 'chat' } },
    ],
  }])

  assert.equal(sessions[0].messages[0].meta.requestId, 'request-1')
  assert.equal(sessions[0].messages[0].meta.status, 'pending')
  assert.equal(sessions[0].messages[1].meta.status, 'completed')
})

test('filterSessionsByTitle returns a copy of all sessions for empty or blank queries', () => {
  const sessions = [{ id: 'a', title: '新的问诊' }, { id: 'b', title: '待缴费用' }]
  const all = filterSessionsByTitle(sessions, '')
  const trimmed = filterSessionsByTitle(sessions, '   ')
  assert.deepEqual(all, sessions)
  assert.deepEqual(trimmed, sessions)
  assert.notEqual(all, sessions)
})

test('filterSessionsByTitle matches titles case-insensitively and trims the query', () => {
  const sessions = [
    { id: 'a', title: '新的问诊' },
    { id: 'b', title: 'Fever Follow-up' },
    { id: 'c', title: '待缴费用' },
  ]
  assert.deepEqual(filterSessionsByTitle(sessions, ' 问诊 '), [{ id: 'a', title: '新的问诊' }])
  assert.deepEqual(filterSessionsByTitle(sessions, 'fever'), [{ id: 'b', title: 'Fever Follow-up' }])
})

test('filterSessionsByTitle returns an empty array without mutating the original list', () => {
  const sessions = [{ id: 'a', title: '新的问诊' }]
  const snapshot = [...sessions]
  assert.deepEqual(filterSessionsByTitle(sessions, '挂号'), [])
  assert.deepEqual(sessions, snapshot)
})

test('toTask only exposes approved patient task types', () => {
  assert.deepEqual(toTask({ type: 'registration', title: '预约挂号' }), { type: 'registration', title: '预约挂号' })
  assert.equal(toTask({ type: 'prescription' }), null)
})

test('toTask keeps payment identifiers for the task sheet', () => {
  assert.deepEqual(toTask({ type: 'payment', chargeId: 12, title: '待缴费用' }), {
    type: 'payment', chargeId: 12, title: '待缴费用',
  })
})

test('patient entry starts in the unified patient home', () => {
  assert.equal(patientHomePath(), '/home')
  assert.equal(isPatientPortal({ portalType: 'patient' }), true)
  assert.equal(isPatientPortal({ portalType: 'doctor' }), false)
})

test('local session can be removed when server has no matching conversation', () => {
  assert.equal(shouldRemoveLocalSessionAfterDeleteError(null, false), true)
  assert.equal(shouldRemoveLocalSessionAfterDeleteError(new Error('无权访问该会话'), false), true)
  assert.equal(shouldRemoveLocalSessionAfterDeleteError(new Error('无权访问该会话'), true), true)
  assert.equal(shouldRemoveLocalSessionAfterDeleteError(new Error('网络异常，请检查网络连接'), false), false)
  assert.equal(shouldRemoveLocalSessionAfterDeleteError(new Error('请求超时'), true), true)
})

test('mode preference round-trips through storage', () => {
  const storage = new Map()
  const local = {
    getItem: (key) => storage.get(key) ?? null,
    setItem: (key, value) => storage.set(key, value),
  }
  writeMode('classic', local)
  assert.equal(local.getItem(MODE_STORAGE_KEY), 'classic')
  assert.equal(readMode(local), 'classic')
})
