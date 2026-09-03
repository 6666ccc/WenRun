const CLINIC_TZ = 'Asia/Shanghai'
/** 与后端 wenrun.clinic.morning-end 默认值保持一致 */
const DEFAULT_MORNING_END = '12:00'
const DEFAULT_AFTERNOON_END = '18:00'
const DEFAULT_EVENING_END = '21:00'

function pad(value) {
  return String(value).padStart(2, '0')
}

function clinicParts(now = new Date()) {
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat('en-GB', {
      timeZone: CLINIC_TZ,
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      hourCycle: 'h23',
    }).formatToParts(now)
      .filter((part) => part.type !== 'literal')
      .map((part) => [part.type, part.value]),
  )
  return {
    date: `${parts.year}-${parts.month}-${parts.day}`,
    minutes: Number(parts.hour) * 60 + Number(parts.minute),
  }
}

function timeToMinutes(value) {
  const [hour, minute] = String(value).split(':').map(Number)
  return hour * 60 + (minute || 0)
}

/** 获取北京时间日历的 ISO 日期（YYYY-MM-DD） */
export function todayISO(now = new Date()) {
  return clinicParts(now).date
}

export function shiftClinicDate(offset, now = new Date()) {
  const [year, month, day] = todayISO(now).split('-').map(Number)
  const shifted = new Date(Date.UTC(year, month - 1, day + offset))
  return `${shifted.getUTCFullYear()}-${pad(shifted.getUTCMonth() + 1)}-${pad(shifted.getUTCDate())}`
}

/** 就诊日期是否仍可预约：今天及以后为 true */
export function isBookableWorkDate(workDate, now = new Date()) {
  if (!workDate) return false
  return String(workDate).slice(0, 10) >= todayISO(now)
}

/**
 * 号源是否仍可预约。当天上午过了 morningEnd（默认 12:00 北京时间）后不再展示。
 */
export function isBookableSchedule(workDate, timePeriod, now = new Date(), morningEnd = DEFAULT_MORNING_END) {
  if (!isBookableWorkDate(workDate, now)) return false
  if (String(workDate).slice(0, 10) !== todayISO(now)) return true
  const { minutes } = clinicParts(now)
  if (timePeriod === '上午') return minutes < timeToMinutes(morningEnd)
  if (timePeriod === '下午') return minutes < timeToMinutes(DEFAULT_AFTERNOON_END)
  if (timePeriod === '晚上') return minutes < timeToMinutes(DEFAULT_EVENING_END)
  return true
}

/** 同一医生、同一天、同一上下午是否已有有效挂号 */
export function isOccupiedSlot(schedule, registrations) {
  if (!schedule || !Array.isArray(registrations)) return false
  const date = String(schedule.workDate || '').slice(0, 10)
  return registrations.some((item) => {
    const status = Number(item.status)
    if (status !== 1 && status !== 2) return false
    return String(item.staffId) === String(schedule.staffId)
      && String(item.workDate || '').slice(0, 10) === date
      && item.timePeriod === schedule.timePeriod
  })
}
