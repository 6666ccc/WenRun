import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

import {
  formatDurationMinutes,
  sleepDurationMinutes,
  toApiDateTime,
  toExercisePayload,
  toSleepPayload,
} from '../src/utils/activity.js'

const here = dirname(fileURLToPath(import.meta.url))
const read = (path) => readFileSync(join(here, path), 'utf8')

test('formatDurationMinutes splits hours and leftover minutes', () => {
  assert.equal(formatDurationMinutes(0), '0 分钟')
  assert.equal(formatDurationMinutes(45), '45 分钟')
  assert.equal(formatDurationMinutes(120), '2 小时')
  assert.equal(formatDurationMinutes(470), '7 小时 50 分钟')
  assert.equal(formatDurationMinutes(null), '—')
})

test('sleepDurationMinutes uses bedtime and wake time', () => {
  assert.equal(sleepDurationMinutes('2026-09-23T23:10', '2026-09-24T07:00'), 470)
  assert.equal(sleepDurationMinutes('2026-09-24T07:00', '2026-09-23T23:10'), null)
})

test('activity payloads send null optionals and seconds on local datetimes', () => {
  assert.equal(toApiDateTime('2026-09-24T07:30'), '2026-09-24T07:30:00')
  assert.deepEqual(toExercisePayload({
    exerciseType: 'RUN',
    durationMin: '35',
    distanceKm: '',
    caloriesKcal: '320',
    intensity: '',
    startedAt: '2026-09-24T07:30',
    remark: '  晨跑  ',
  }), {
    exerciseType: 'RUN',
    durationMin: 35,
    distanceKm: null,
    caloriesKcal: 320,
    intensity: null,
    startedAt: '2026-09-24T07:30:00',
    remark: '晨跑',
  })
  assert.equal(toSleepPayload({
    bedtime: '2026-09-23T23:10',
    wakeTime: '2026-09-24T07:00',
    quality: 5,
    remark: '',
  }).bedtime, '2026-09-23T23:10:00')
})

test('archive activity tab records exercise and sleep instead of the unavailable shell', () => {
  const page = read('../src/views/PatientArchive.vue')
  const activity = read('../src/components/archive/ArchiveActivity.vue')
  assert.match(page, /ArchiveActivity/)
  assert.doesNotMatch(page, /暂未接入运动与睡眠数据/)
  assert.match(activity, /记录运动/)
  assert.match(activity, /记录睡眠/)
  assert.match(activity, /createExercise/)
  assert.match(activity, /createSleepRecord/)
})
