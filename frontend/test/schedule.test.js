import test from 'node:test'
import assert from 'node:assert/strict'

import {
  isBookableSchedule,
  isOccupiedSlot,
  todayISO,
} from '../src/utils/scheduleDate.js'

test('isBookableWorkDate hides past duty dates from the booking list', () => {
  const now = new Date('2026-09-03T15:21:00+08:00')
  assert.equal(todayISO(now), '2026-09-03')
  assert.equal(isBookableSchedule('2026-09-01', '下午', now), false)
  assert.equal(isBookableSchedule('2026-09-03', '下午', now), true)
  assert.equal(isBookableSchedule('2026-09-04', '上午', now), true)
  assert.equal(isBookableSchedule('', '上午', now), false)
  assert.equal(isBookableSchedule(null, '上午', now), false)
})

test('morning slots disappear after configured Beijing noon', () => {
  const afterNoon = new Date('2026-09-03T13:00:00+08:00')
  const beforeNoon = new Date('2026-09-03T11:59:00+08:00')
  assert.equal(isBookableSchedule('2026-09-03', '上午', afterNoon, '12:00'), false)
  assert.equal(isBookableSchedule('2026-09-03', '下午', afterNoon, '12:00'), true)
  assert.equal(isBookableSchedule('2026-09-03', '上午', beforeNoon, '12:00'), true)
  assert.equal(isBookableSchedule('2026-09-03', '上午', new Date('2026-09-03T11:30:00+08:00'), '11:00'), false)
})

test('isOccupiedSlot blocks the same doctor on the same day and period', () => {
  const schedule = { staffId: 8, workDate: '2026-09-03', timePeriod: '下午' }
  const mine = [
    { staffId: 8, workDate: '2026-09-03', timePeriod: '下午', status: 1 },
  ]
  assert.equal(isOccupiedSlot(schedule, mine), true)
  assert.equal(isOccupiedSlot({ ...schedule, timePeriod: '上午' }, mine), false)
  assert.equal(isOccupiedSlot(schedule, [{ ...mine[0], status: 3 }]), false)
})
