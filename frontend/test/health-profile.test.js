import test from 'node:test'
import assert from 'node:assert/strict'

import {
  METRIC_EDITORS,
  calcBmi,
  calcWhtr,
  fillHealthForm,
  formatBloodPressure,
  formatGlucoseType,
  isMetricEditor,
  metricEditor,
  toDatetimeLocal,
  toHealthPayload,
} from '../src/utils/healthProfile.js'

test('formatGlucoseType maps fasting to 空腹', () => {
  assert.equal(formatGlucoseType('fasting'), '空腹')
  assert.equal(formatGlucoseType(''), '')
})

test('formatBloodPressure keeps incomplete pairs readable', () => {
  assert.equal(formatBloodPressure(118, 76), '118 / 76')
  assert.equal(formatBloodPressure(118, null), '118 / —')
  assert.equal(formatBloodPressure(null, null), '')
})

test('calcBmi returns one decimal from cm and kg', () => {
  assert.equal(calcBmi(170, 62.5), '21.6')
  assert.equal(calcBmi('', 62.5), '')
})

test('calcWhtr returns three decimals from cm values', () => {
  assert.equal(calcWhtr(170, 85), '0.500')
  assert.equal(calcWhtr('', 85), '')
})

test('toHealthPayload blanks empty numbers and trims histories', () => {
  const payload = toHealthPayload({
    heightCm: '170.0',
    weightKg: '',
    waistCm: '85.5',
    systolicMmhg: '118',
    diastolicMmhg: '',
    glucoseMmol: '',
    glucoseType: '',
    heartRateBpm: '',
    measuredAt: '2026-09-19T08:30',
    pastHistory: '  无手术史  ',
    familyHistory: '',
    personalHistory: '',
  })
  assert.equal(payload.heightCm, 170)
  assert.equal(payload.weightKg, null)
  assert.equal(payload.waistCm, 85.5)
  assert.equal(payload.pastHistory, '无手术史')
  assert.equal(payload.measuredAt, '2026-09-19T08:30')
})

test('toHealthPayload maps spo2 respiratory rate and temperature', () => {
  const payload = toHealthPayload({
    spo2Pct: '98',
    respiratoryRateBpm: '16',
    temperatureC: '36.5',
    pastHistory: '',
    familyHistory: '',
    personalHistory: '',
  })
  assert.equal(payload.spo2Pct, 98)
  assert.equal(payload.respiratoryRateBpm, 16)
  assert.equal(payload.temperatureC, 36.5)
})

test('fillHealthForm converts ISO measuredAt for datetime-local', () => {
  const form = fillHealthForm({
    heightCm: 170,
    measuredAt: '2026-09-19T08:30:00',
  })
  assert.equal(form.heightCm, 170)
  assert.equal(toDatetimeLocal('2026-09-19T08:30:00'), '2026-09-19T08:30')
  assert.equal(form.measuredAt, '2026-09-19T08:30')
})

test('metric editors cover nine recordable ids and not derived metrics', () => {
  assert.deepEqual(Object.keys(METRIC_EDITORS), ['weight', 'waist', 'height', 'bp', 'glucose', 'hr', 'spo2', 'rr', 'temp'])
  assert.equal(isMetricEditor('bp'), true)
  assert.equal(isMetricEditor('vitals'), false)
  assert.equal(isMetricEditor('body'), false)
  assert.equal(isMetricEditor('bmi'), false)
  assert.equal(isMetricEditor('whtr'), false)
  assert.equal(metricEditor('unknown'), null)
})

test('metric editor fields match the focused dialog spec', () => {
  const keys = (id) => metricEditor(id).fields.map((field) => field.key)
  assert.equal(metricEditor('weight').title, '记录体重')
  assert.deepEqual(keys('weight'), ['weightKg'])
  assert.deepEqual(keys('waist'), ['waistCm'])
  assert.deepEqual(keys('height'), ['heightCm'])
  assert.deepEqual(keys('bp'), ['systolicMmhg', 'diastolicMmhg'])
  assert.deepEqual(keys('glucose'), ['glucoseMmol', 'glucoseType'])
  assert.deepEqual(keys('hr'), ['heartRateBpm'])
  assert.deepEqual(keys('spo2'), ['spo2Pct'])
  assert.deepEqual(keys('rr'), ['respiratoryRateBpm'])
  assert.deepEqual(keys('temp'), ['temperatureC'])
  assert.equal(metricEditor('glucose').fields[1].type, 'select')
})
