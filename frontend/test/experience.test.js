import test from 'node:test'
import assert from 'node:assert/strict'

import { MODE_AGENT, MODE_CLASSIC, MODE_STORAGE_KEY, normalizeMode, patientHomePath, isPatientPortal, readMode, writeMode } from '../src/features/experience/mode.js'
import { filterSessionsByTitle, normalizeSessions } from '../src/features/assistant/session.js'
import { toTask } from '../src/features/assistant/task.js'

test('normalizeMode only accepts the two patient experiences', () => {
  assert.equal(normalizeMode('agent'), MODE_AGENT)
  assert.equal(normalizeMode('classic'), MODE_CLASSIC)
  assert.equal(normalizeMode('doctor'), MODE_AGENT)
})

test('normalizeSessions recovers a safe default after corrupt storage', () => {
  assert.deepEqual(normalizeSessions('{broken json'), [{ id: 'default', title: '新的问诊', messages: [], pendingInterrupt: null }])
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
