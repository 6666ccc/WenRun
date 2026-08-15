/**
 * 通用工具函数 + 状态映射表
 */

/* ---------- 时间问候语 ---------- */
export function formatTime() {
  const h = new Date().getHours()
  if (h < 6)  return '夜深了'
  if (h < 9)  return '早上好'
  if (h < 12) return '上午好'
  if (h < 14) return '中午好'
  if (h < 18) return '下午好'
  return '晚上好'
}

/* ---------- 金额格式化 ---------- */
export function formatMoney(v) {
  if (v == null) return '¥0.00'
  return `¥${Number(v).toFixed(2)}`
}

/* ---------- 日期格式化 ---------- */
export function formatDate(v) {
  if (!v) return ''
  const d = new Date(v)
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

/* ---------- 日期时间格式化 ---------- */
export function formatDateTime(v) {
  if (!v) return ''
  const d = new Date(v)
  const date = formatDate(v)
  const hh = String(d.getHours()).padStart(2, '0')
  const mm = String(d.getMinutes()).padStart(2, '0')
  return `${date} ${hh}:${mm}`
}

/* ---------- 文本截断 ---------- */
export function truncate(text, maxLen = 20) {
  if (!text) return ''
  return text.length > maxLen ? text.slice(0, maxLen) + '…' : text
}

/* ---------- 获取 today 的 ISO 日期字符串 ---------- */
export function todayISO() {
  return formatDate(new Date())
}

/* ====== 状态映射表 ====== */

/** 挂号状态 */
export const REG_STATUS_MAP = {
  1: { label: '已挂号', cls: 'shared-status--pending' },
  2: { label: '已就诊', cls: 'shared-status--active' },
  3: { label: '已退号', cls: 'shared-status--cancelled' },
}

/** 就诊状态 */
export const VISIT_STATUS_MAP = {
  1: { label: '接诊中', cls: 'shared-status--active' },
  2: { label: '已完成', cls: 'shared-status--done' },
}

/** 支付状态 */
export const PAY_STATUS_MAP = {
  0: { label: '待支付', cls: 'shared-status--pending' },
  1: { label: '已支付', cls: 'shared-status--paid' },
  2: { label: '已退款', cls: 'shared-status--refund' },
}

/** 处方状态 */
export const RX_STATUS_MAP = {
  1: { label: '待缴费', cls: 'shared-status--pending' },
  2: { label: '已缴费', cls: 'shared-status--paid' },
  3: { label: '已发药', cls: 'shared-status--done' },
  4: { label: '已作废', cls: 'shared-status--cancelled' },
}

/** 检查申请状态 */
export const EXAM_STATUS_MAP = {
  1: { label: '待缴费', cls: 'shared-status--pending' },
  2: { label: '已缴费', cls: 'shared-status--paid' },
}

/** 性别 */
export const GENDER_MAP = {
  0: '女',
  1: '男',
  2: '未知',
}

/** 支付方式 */
export const PAY_TYPE_MAP = {
  1: '现金',
  2: '微信',
  3: '支付宝',
  4: '医保',
}

/** 排班时段 */
export const PERIOD_MAP = {
  morning: '上午',
  afternoon: '下午',
  evening: '晚上',
  上午: '上午',
  下午: '下午',
  晚上: '晚上',
}

/** 排班时段文案 */
export function formatTimePeriod(period) {
  if (!period) return ''
  return PERIOD_MAP[period] || period
}

/** 就诊时间：排班日期 + 时段 */
export function formatVisitSchedule(workDate, timePeriod) {
  if (!workDate) return '—'
  const date = formatDate(workDate)
  const period = formatTimePeriod(timePeriod)
  return period ? `${date} ${period}` : date
}

/** 通用状态文本获取 */
export function getStatusLabel(item) {
  if (!item) return ''
  const map =
    REG_STATUS_MAP[item.status] ||
    VISIT_STATUS_MAP[item.status] ||
    PAY_STATUS_MAP[item.payStatus] ||
    RX_STATUS_MAP[item.status] ||
    EXAM_STATUS_MAP[item.status]
  return map?.label || '未知'
}

export { homePath, isPatientPortal } from './portal'
