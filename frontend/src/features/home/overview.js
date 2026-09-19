import { isBookableSchedule } from '../../utils/scheduleDate.js'

const asList = (value) => (Array.isArray(value) ? value : [])

/** 首页"下次就诊"取第一条待就诊（status === 1）的挂号。 */
export function nextAppointment(registrations) {
  return asList(registrations).find((item) => Number(item?.status) === 1) || null
}

/** 首页"今日可预约"：有余号且未过时段截止的号源，最多 limit 条。 */
export function bookableToday(schedules, limit = 3, now = new Date()) {
  return asList(schedules)
    .filter((item) => Number(item?.remainingCount) > 0 && isBookableSchedule(item?.workDate, item?.timePeriod, now))
    .slice(0, limit)
}
