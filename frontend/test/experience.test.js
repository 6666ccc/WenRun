import test from 'node:test'
import assert from 'node:assert/strict'

import { MODE_AGENT, MODE_CLASSIC, MODE_STORAGE_KEY, normalizeMode, patientHomePath, isPatientPortal, readMode, writeMode } from '../src/features/experience/mode.js'
import { normalizeSessions } from '../src/features/assistant/session.js'
import { toTask } from '../src/features/assistant/task.js'

test('normalizeMode only accepts the two patient experiences', () => {
  assert.equal(normalizeMode('agent'), MODE_AGENT)
  assert.equal(normalizeMode('classic'), MODE_CLASSIC)
  assert.equal(normalizeMode('doctor'), MODE_AGENT)
})

test('normalizeSessions recovers a safe default after corrupt storage', () => {
  assert.deepEqual(normalizeSessions('{broken json'), [{ id: 'default', title: '新的问诊', messages: [] }])
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

test('patient entry always starts with the experience selector', () => {
  assert.equal(patientHomePath(), '/mode-select')
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
