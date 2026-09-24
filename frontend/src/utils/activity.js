import { toDatetimeLocal } from './healthProfile.js'

export const EXERCISE_TYPES = [
  { code: 'WALK', name: '步行' },
  { code: 'RUN', name: '跑步' },
  { code: 'CYCLE', name: '骑行' },
  { code: 'SWIM', name: '游泳' },
  { code: 'STRENGTH', name: '力量训练' },
  { code: 'YOGA', name: '瑜伽' },
  { code: 'BALL', name: '球类' },
  { code: 'OTHER', name: '其他' },
]

export const EXERCISE_INTENSITIES = [
  { code: 'LOW', name: '轻松' },
  { code: 'MODERATE', name: '中等' },
  { code: 'HIGH', name: '剧烈' },
]

export const SLEEP_QUALITIES = [
  { code: 1, name: '很差' },
  { code: 2, name: '较差' },
  { code: 3, name: '一般' },
  { code: 4, name: '较好' },
  { code: 5, name: '很好' },
]

export function formatDurationMinutes(minutes) {
  if (minutes == null || minutes === '') return '—'
  const value = Number(minutes)
  if (!Number.isFinite(value) || value < 0) return '—'
  const total = Math.round(value)
  const hours = Math.floor(total / 60)
  const mins = total % 60
  if (hours === 0) return `${mins} 分钟`
  if (mins === 0) return `${hours} 小时`
  return `${hours} 小时 ${mins} 分钟`
}

export function sleepDurationMinutes(bedtime, wakeTime) {
  if (!bedtime || !wakeTime) return null
  const start = new Date(bedtime)
  const end = new Date(wakeTime)
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime()) || end <= start) return null
  return Math.round((end.getTime() - start.getTime()) / 60000)
}

export function toApiDateTime(value) {
  if (!value) return null
  if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(value)) return `${value}:00`
  return value
}

export function emptyExerciseForm() {
  return {
    exerciseType: 'WALK',
    durationMin: '',
    distanceKm: '',
    caloriesKcal: '',
    intensity: '',
    startedAt: '',
    remark: '',
  }
}

export function emptySleepForm() {
  return {
    bedtime: '',
    wakeTime: '',
    quality: 4,
    remark: '',
  }
}

function optionalNumber(value) {
  if (value === '' || value == null) return null
  const next = Number(value)
  return Number.isFinite(next) ? next : null
}

export function toExercisePayload(form) {
  return {
    exerciseType: form.exerciseType,
    durationMin: optionalNumber(form.durationMin),
    distanceKm: optionalNumber(form.distanceKm),
    caloriesKcal: optionalNumber(form.caloriesKcal),
    intensity: form.intensity || null,
    startedAt: toApiDateTime(form.startedAt),
    remark: form.remark?.trim() || null,
  }
}

export function toSleepPayload(form) {
  return {
    bedtime: toApiDateTime(form.bedtime),
    wakeTime: toApiDateTime(form.wakeTime),
    quality: Number(form.quality),
    remark: form.remark?.trim() || null,
  }
}

export function fillExerciseForm(record = {}) {
  return {
    exerciseType: record.exerciseType || 'WALK',
    durationMin: record.durationMin ?? '',
    distanceKm: record.distanceKm ?? '',
    caloriesKcal: record.caloriesKcal ?? '',
    intensity: record.intensity || '',
    startedAt: toDatetimeLocal(record.startedAt),
    remark: record.remark || '',
  }
}

export function fillSleepForm(record = {}) {
  return {
    bedtime: toDatetimeLocal(record.bedtime),
    wakeTime: toDatetimeLocal(record.wakeTime),
    quality: record.quality ?? 4,
    remark: record.remark || '',
  }
}
