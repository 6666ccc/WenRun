import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

import { archiveDialogFromQuery, archiveTabFromQuery, calcAge, maskIdCard } from '../src/features/archive/tabs.js'

const here = dirname(fileURLToPath(import.meta.url))
const read = (path) => readFileSync(join(here, path), 'utf8')

test('archiveTabFromQuery defaults unknown or empty values to health', () => {
  assert.equal(archiveTabFromQuery(), 'health')
  assert.equal(archiveTabFromQuery(''), 'health')
  assert.equal(archiveTabFromQuery('nope'), 'health')
  assert.equal(archiveTabFromQuery('basic'), 'health')
  assert.equal(archiveTabFromQuery('history'), 'health')
  assert.equal(archiveTabFromQuery('trend'), 'trend')
  assert.equal(archiveTabFromQuery('registrations'), 'registrations')
})

test('archiveDialogFromQuery opens basic and history as dialogs', () => {
  assert.equal(archiveDialogFromQuery(), '')
  assert.equal(archiveDialogFromQuery('health'), '')
  assert.equal(archiveDialogFromQuery('basic'), 'basic')
  assert.equal(archiveDialogFromQuery('history'), 'history')
})

test('calcAge uses birthday and returns empty when missing', () => {
  assert.equal(calcAge('', new Date('2026-09-19')), '')
  assert.equal(calcAge('2001-09-19', new Date('2026-09-19')), '25')
  assert.equal(calcAge('2001-09-20', new Date('2026-09-19')), '24')
})

test('maskIdCard hides the middle digits', () => {
  assert.equal(maskIdCard(''), '—')
  assert.equal(maskIdCard('110101200109191234'), '1101 •••••• 1234')
})

test('archive page marks undesigned modules instead of snapshot APIs', () => {
  const page = read('../src/views/PatientArchive.vue')
  const unavailable = read('../src/components/archive/ArchiveUnavailable.vue')
  assert.match(unavailable, /数据库还未设计/)
  assert.doesNotMatch(page, /listHealthSnapshots|deleteHealthSnapshot|deleteHealthProfile/)
})

test('archive page queries patient medical data by activePatientId not userId', () => {
  const page = read('../src/views/PatientArchive.vue')
  const auth = read('../src/stores/auth.js')
  const booking = read('../src/components/workspace/RegistrationBooking.vue')
  const record = read('../src/components/workspace/RegistrationRecord.vue')
  const assistant = read('../src/composables/useAssistant.js')
  assert.match(auth, /activePatientId/)
  assert.match(page, /activePatientId/)
  assert.doesNotMatch(page, /listRegistrations\(\{ userId/)
  assert.match(page, /listRegistrations\(\{ patientId/)
  assert.doesNotMatch(booking, /userId: user\.value\.userId/)
  assert.match(booking, /patientId: activePatientId/)
  assert.doesNotMatch(record, /userId: user\.value\.userId/)
  assert.match(record, /patientId: activePatientId/)
  assert.doesNotMatch(assistant, /listRegistrations\(\{ userId/)
  assert.match(assistant, /patientId: user\.value\?\.activePatientId/)
})

test('archive page does not wrap itself in the patient service sidebar', () => {
  const page = read('../src/views/PatientArchive.vue')
  assert.doesNotMatch(page, /AppShell/)
  assert.match(page, /MobileTabbar/)
})

test('archive page opens basic and history forms in a dialog over health data', () => {
  const page = read('../src/views/PatientArchive.vue')
  assert.doesNotMatch(page, /id: 'basic', label: '基本资料'/)
  assert.doesNotMatch(page, /id: 'history', label: '健康信息'/)
  assert.match(page, /editor === 'basic'/)
  assert.match(page, /editor === 'history'/)
  assert.match(page, /基本资料/)
})

test('archive page renders metric editors from config instead of grouped body/vitals forms', () => {
  const page = read('../src/views/PatientArchive.vue')
  assert.match(page, /metricEditor/)
  assert.match(page, /isMetricEditor/)
  assert.doesNotMatch(page, /editor === 'body'/)
  assert.doesNotMatch(page, /editor === 'vitals'/)
  assert.doesNotMatch(page, /记录生命体征/)
  assert.match(page, /healthForm\.measuredAt/)
})

test('medical document cards live on the documents tab, not health data', () => {
  const page = read('../src/views/PatientArchive.vue')
  const health = read('../src/components/archive/ArchiveHealthData.vue')
  const docs = read('../src/components/archive/ArchiveDocuments.vue')
  const sidebar = read('../src/components/archive/ArchiveSidebar.vue')
  assert.match(page, /ArchiveDocuments/)
  assert.doesNotMatch(page, /v-else-if="tab === 'documents'" title="就医资料"/)
  assert.doesNotMatch(health, /就医资料/)
  assert.doesNotMatch(health, /doc-grid/)
  assert.match(docs, /病历/)
  assert.match(docs, /报告单/)
  assert.match(docs, /药物/)
  assert.match(docs, /体检报告/)
  assert.match(docs, /上传资料/)
  assert.match(sidebar, /emit\('open-tab', 'documents'\)/)
})
