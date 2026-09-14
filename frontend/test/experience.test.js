import test from 'node:test'
import assert from 'node:assert/strict'

import { MODE_AGENT, MODE_CLASSIC, MODE_STORAGE_KEY, normalizeMode, patientHomePath, isPatientPortal, readMode, writeMode } from '../src/features/experience/mode.js'
import { filterSessionsByTitle, normalizeServerConversations, normalizeSessions, readOwnedLegacySessions, sessionHasPendingConfirm, shouldRemoveLocalSessionAfterDeleteError } from '../src/features/assistant/session.js'
import { toTask } from '../src/features/assistant/task.js'

test('normalizeMode only accepts the two patient experiences', () => {
  assert.equal(normalizeMode('agent'), MODE_AGENT)
  assert.equal(normalizeMode('classic'), MODE_CLASSIC)
  assert.equal(normalizeMode('doctor'), MODE_AGENT)
})

test('normalizeSessions recovers a unique session after corrupt storage', () => {
  const sessions = normalizeSessions('{broken json')
  assert.equal(sessions.length, 1)
  assert.equal(sessions[0].title, '新的问诊')
  assert.deepEqual(sessions[0].messages, [])
  assert.notEqual(sessions[0].id, 'default')
  assert.match(sessions[0].id, /^session_\d+_[0-9a-f]+$/)
})

test('normalizeSessions migrates the shared default conversation id', () => {
  const sessions = normalizeSessions([{
    id: 'default',
    title: '旧会话',
    messages: [{ role: 'user', content: '你好' }],
  }])
  assert.equal(sessions.length, 1)
  assert.notEqual(sessions[0].id, 'default')
  assert.match(sessions[0].id, /^session_\d+_[0-9a-f]+$/)
  assert.equal(sessions[0].title, '旧会话')
  assert.equal(sessions[0].messages[0].content, '你好')
})

test('legacy browser history is never shown after switching accounts', () => {
  const storage = {
    wenrun_ai_sessions_owner: 'user-a',
    wenrun_ai_sessions: JSON.stringify([{
      id: 'private-a',
      title: 'A 的会话',
      messages: [{ role: 'user', content: 'A 的隐私内容' }],
    }]),
    getItem(key) { return this[key] ?? null },
    setItem(key, value) { this[key] = value },
  }

  const sessions = readOwnedLegacySessions(storage, 'user-b')

  assert.equal(sessions.length, 1)
  assert.deepEqual(sessions[0].messages, [])
  assert.notEqual(sessions[0].id, 'private-a')
})

test('server conversations restore messages and pending confirmation metadata', () => {
  const sessions = normalizeServerConversations(
    [{ conversationId: 'c1', title: '挂号', messageCount: 2 }],
    { c1: [
      { id: 1, role: 'user', content: '帮我挂号', clientRequestId: 'r1' },
      {
        id: 2,
        role: 'assistant',
        content: '请确认',
        clientRequestId: 'r1',
        metadata: { status: 'confirming', confirm: { interruptId: 'i1' } },
      },
    ] },
  )

  assert.equal(sessions[0].id, 'c1')
  assert.equal(sessions[0].messages[1].meta.status, 'confirming')
  assert.equal(sessions[0].messages[1].meta.confirm.interruptId, 'i1')
  assert.equal(sessionHasPendingConfirm(sessions[0]), true)
})

test('sessionHasPendingConfirm detects an unanswered confirmation card', () => {
  assert.equal(sessionHasPendingConfirm({
    messages: [{ role: 'assistant', meta: { status: 'confirming', confirm: { kind: 'registration_create' } } }],
  }), true)
  assert.equal(sessionHasPendingConfirm({
    messages: [{ role: 'assistant', meta: { status: 'completed' } }],
  }), false)
  assert.equal(sessionHasPendingConfirm(null), false)
})

test('sessionHasPendingConfirm ignores a user message stuck in confirming status', () => {
  assert.equal(sessionHasPendingConfirm({
    messages: [{ role: 'user', meta: { status: 'confirming' } }],
  }), false)
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
