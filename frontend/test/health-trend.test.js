import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

import { shouldSkipAuth } from '../src/api/authSkip.js'
import {
  TREND_RANGES,
  buildChartOption,
  formatTrendTime,
  summarizeTrend,
} from '../src/features/archive/trend.js'

const here = dirname(fileURLToPath(import.meta.url))

test('health check skip auth does not apply to metric trend API', () => {
  assert.equal(shouldSkipAuth('/api/health'), true)
  assert.equal(shouldSkipAuth('/api/auth/login'), true)
  assert.equal(shouldSkipAuth('/api/health-metrics/types'), false)
  assert.equal(shouldSkipAuth('/api/patients/3/health-metrics/trend'), false)
})

test('trend ranges match backend 7/30/90/365', () => {
  assert.deepEqual(TREND_RANGES.map((item) => item.days), [7, 30, 90, 365])
  assert.equal(TREND_RANGES.find((item) => item.days === 90).label, '近3月')
})

test('summarizeTrend shows latest weight and down change', () => {
  const summary = summarizeTrend('WEIGHT', 'kg', [
    { primaryValue: 106.2, measuredAt: '2026-09-01T08:30:00' },
    { primaryValue: 103.5, measuredAt: '2026-09-18T07:00:00' },
  ])
  assert.equal(summary.displayValue, '103.5')
  assert.equal(summary.unit, 'kg')
  assert.equal(summary.changeKind, 'down')
  assert.match(summary.changeText, /↓/)
  assert.equal(summary.latestTime, '最近记录：2026-09-18')
})

test('summarizeTrend formats blood pressure as dual values', () => {
  const summary = summarizeTrend('BLOOD_PRESSURE', 'mmHg', [
    { primaryValue: 128, secondaryValue: 82, measuredAt: '2026-09-01T08:30:00' },
  ])
  assert.equal(summary.displayValue, '128/82')
  assert.equal(summary.changeKind, 'normal')
  assert.equal(summary.changeText, '血压趋势')
})

test('summarizeTrend empty records stay placeholder', () => {
  const summary = summarizeTrend('WEIGHT', 'kg', [])
  assert.equal(summary.displayValue, '--')
  assert.equal(summary.changeText, '暂无变化')
  assert.equal(summary.latestTime, '最近记录：--')
})

test('buildChartOption uses one series except blood pressure', () => {
  const weight = buildChartOption('WEIGHT', '体重', 'kg', [
    { primaryValue: 103.5, measuredAt: '2026-09-18T07:00:00' },
  ])
  assert.equal(weight.series.length, 1)
  assert.equal(weight.series[0].data[0], 103.5)
  assert.equal(weight.xAxis.data[0], '09-18')

  const bp = buildChartOption('BLOOD_PRESSURE', '血压', 'mmHg', [
    { primaryValue: 128, secondaryValue: 82, measuredAt: '2026-09-01T08:30:00' },
  ])
  assert.equal(bp.series.length, 2)
  assert.deepEqual(bp.legend.data, ['收缩压', '舒张压'])
  assert.equal(bp.series[0].data[0], 128)
  assert.equal(bp.series[1].data[0], 82)
})

test('formatTrendTime keeps calendar date for axis/summary', () => {
  assert.equal(formatTrendTime('2026-09-01T08:30:00'), '2026-09-01')
  assert.equal(formatTrendTime(''), '')
})

test('archive health trend has its own tab and uses the live metric API', () => {
  const healthData = readFileSync(join(here, '../src/components/archive/ArchiveHealthData.vue'), 'utf8')
  const page = readFileSync(join(here, '../src/views/PatientArchive.vue'), 'utf8')
  const trend = readFileSync(join(here, '../src/components/archive/ArchiveHealthTrend.vue'), 'utf8')
  const helpers = readFileSync(join(here, '../src/features/archive/trend.js'), 'utf8')
  const api = readFileSync(join(here, '../src/api/modules/healthMetric.js'), 'utf8')
  assert.doesNotMatch(healthData, /ArchiveHealthTrend/)
  assert.match(page, /id: 'trend', label: '健康趋势'/)
  assert.match(page, /v-else-if="item\.id === 'trend'"/)
  assert.doesNotMatch(healthData, /ArchiveUnavailable title="健康趋势"/)
  assert.match(trend, /getHealthMetricTrend/)
  assert.match(trend, /patientId/)
  assert.match(api, /\/api\/patients\/\$\{patientId\}\/health-metrics\/trend/)
  assert.match(trend, /refreshKey/)
  assert.match(page, /refresh-key/)
  assert.match(helpers, /近3月/)
})

test('archive metric cards emit one editor id each and drop group record links', () => {
  const healthData = readFileSync(join(here, '../src/components/archive/ArchiveHealthData.vue'), 'utf8')
  assert.doesNotMatch(healthData, /记录数据/)
  assert.doesNotMatch(healthData, /emit\('record', 'body'\)/)
  assert.doesNotMatch(healthData, /emit\('record', 'vitals'\)/)
  assert.match(healthData, /emit\('record', 'weight'\)/)
  assert.match(healthData, /emit\('record', 'height'\)/)
  assert.match(healthData, /emit\('record', 'waist'\)/)
  assert.match(healthData, /health\?\.waistCm/)
  assert.match(healthData, /emit\('record', 'bp'\)/)
  assert.match(healthData, /emit\('record', 'glucose'\)/)
  assert.match(healthData, /emit\('record', 'hr'\)/)
  assert.match(healthData, /emit\('record', 'spo2'\)/)
  assert.match(healthData, /emit\('record', 'rr'\)/)
  assert.match(healthData, /emit\('record', 'temp'\)/)
  assert.match(healthData, /health\?\.spo2Pct/)
  assert.match(healthData, /health\?\.respiratoryRateBpm/)
  assert.match(healthData, /health\?\.temperatureC/)
  assert.doesNotMatch(healthData, /emit\('unavailable', '血氧'\)/)
  assert.doesNotMatch(healthData, /emit\('unavailable', '腰围'\)/)
})
