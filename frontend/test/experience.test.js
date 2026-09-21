import test from 'node:test'
import assert from 'node:assert/strict'

import { assistantRedirect, patientHomePath, isPatientPortal, userArchiveRedirect } from '../src/features/experience/mode.js'
import { filterSessionsByTitle, normalizeServerConversations, normalizeSessions, readOwnedLegacySessions, sessionHasPendingConfirm, shouldRemoveLocalSessionAfterDeleteError } from '../src/features/assistant/session.js'
import { bookableToday, nextAppointment } from '../src/features/home/overview.js'
import { workspacePanelFor } from '../src/features/experience/workspace.js'

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

test('workspacePanelFor maps patient service paths to home drawers', () => {
  assert.deepEqual(workspacePanelFor('/registration', {}), { kind: 'registration' })
  assert.deepEqual(workspacePanelFor('/registration/12', { id: '12' }), { kind: 'record', id: '12' })
  assert.equal(workspacePanelFor('/user', {}), null)
  assert.equal(workspacePanelFor('/archive', {}), null)
  assert.equal(workspacePanelFor('/home', {}), null)
  assert.equal(workspacePanelFor('/login', {}), null)
})

test('userArchiveRedirect sends legacy personal center to the archive page', () => {
  assert.equal(userArchiveRedirect(), '/archive')
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

test('assistantRedirect folds the legacy assistant route into home and keeps query', () => {
  assert.deepEqual(
    assistantRedirect({ path: '/assistant', query: { prompt: '你好', preview: '1' } }),
    { path: '/home', query: { prompt: '你好', preview: '1' } },
  )
  assert.deepEqual(assistantRedirect({ path: '/assistant', query: {} }), { path: '/home', query: {} })
  assert.deepEqual(assistantRedirect({ path: '/assistant' }), { path: '/home', query: {} })
})

test('nextAppointment picks the first pending registration only', () => {
  const registrations = [
    { id: 1, status: 3, deptName: '已取消' },
    { id: 2, status: 1, deptName: '心内科' },
    { id: 3, status: 1, deptName: '呼吸内科' },
  ]
  assert.equal(nextAppointment(registrations)?.id, 2)
  assert.equal(nextAppointment([{ id: 9, status: 2 }]), null)
  assert.equal(nextAppointment(null), null)
})

test('bookableToday keeps only bookable schedules with remaining count and caps the list', () => {
  const now = new Date('2026-09-19T01:00:00Z') // 北京时间 09:00
  const schedules = [
    { id: 1, workDate: '2026-09-19', timePeriod: '上午', remainingCount: 8 },
    { id: 2, workDate: '2026-09-19', timePeriod: '下午', remainingCount: 0 },
    { id: 3, workDate: '2026-09-18', timePeriod: '上午', remainingCount: 5 },
    { id: 4, workDate: '2026-09-19', timePeriod: '下午', remainingCount: 2 },
    { id: 5, workDate: '2026-09-20', timePeriod: '上午', remainingCount: 1 },
    { id: 6, workDate: '2026-09-20', timePeriod: '下午', remainingCount: 1 },
  ]
  assert.deepEqual(bookableToday(schedules, 3, now).map((item) => item.id), [1, 4, 5])
  assert.deepEqual(bookableToday(undefined, 3, now), [])
})
