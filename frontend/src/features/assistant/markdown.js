const INTERNAL_ID = /[（(]?\s*(?:排班id|挂号单id)\s*=\s*\d+\s*[)）]?/gi
const PAREN_ID = /[（(]\s*id\s*=\s*\d+\s*[)）]/gi
const DAY_LINE = /^(\d{1,2}月\d{1,2}日)(?:[（(]([^)）]+)[)）])?$/
const DAY_HTML = /<(p|h[1-6])>(?:\s*<strong>)?\s*(\d{1,2}月\d{1,2}日(?:[（(][^)）]+[)）])?)\s*(?:<\/strong>\s*)?<\/\1>/gi
const PERIODS = '上午|下午|晚上'

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

function stripTags(html) {
  return String(html)
    .replace(/<[^>]+>/g, ' ')
    .replace(/&nbsp;/g, ' ')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/\s+/g, ' ')
    .trim()
}

function formatFee(value) {
  const amount = Number(value)
  if (Number.isNaN(amount)) return value
  return Number.isInteger(amount) ? String(amount) : amount.toFixed(2)
}

export function stripInternalIds(text) {
  return String(text || '')
    .replace(INTERNAL_ID, '')
    .replace(PAREN_ID, '')
    .replace(/[ \t]{2,}/g, ' ')
    .replace(/[ \t]+([，。！？、])/g, '$1')
    .replace(/[ \t]+\n/g, '\n')
    .replace(/\n[ \t]+/g, '\n')
    .replace(/[ \t]+$/gm, '')
}

export function parseSlotLine(text) {
  const raw = String(text || '').replace(/\s+/g, ' ').trim()
  const periodMatch = raw.match(new RegExp(`^(${PERIODS})(?:\\s+|：|:)`))
  const period = periodMatch?.[1] || ''
  let body = period ? raw.slice(periodMatch[0].length).trim() : raw
  const remaining = body.match(/余号\s*([\d./]+)/)?.[1] || ''
  const fee = body.match(/挂号费\s*([\d.]+)/)?.[1] || ''
  const doctors = body
    .replace(/，?\s*余号\s*[\d./]+/g, '')
    .replace(/，?\s*挂号费\s*[\d.]+\s*元?/g, '')
    .replace(/[，,]\s*$/g, '')
    .split(/\s*[／/、]\s*/)
    .map((item) => item.trim())
    .filter(Boolean)
  return { raw, period, doctors, remaining, fee }
}

export function isScheduleSlot(slot) {
  if (!slot) return false
  return Boolean(slot.period || slot.remaining || slot.fee)
}

function renderDay(label) {
  const match = String(label).trim().match(DAY_LINE)
  if (!match) return `<p class="chat-day">${escapeHtml(label)}</p>`
  const note = match[2]
    ? `<span class="chat-day__note">${escapeHtml(match[2])}</span>`
    : ''
  return `<p class="chat-day"><span class="chat-day__date">${escapeHtml(match[1])}</span>${note}</p>`
}

function renderSlot(slot) {
  if (!isScheduleSlot(slot)) {
    return `<article class="chat-slot"><div class="chat-slot__body"><strong>${escapeHtml(slot.raw)}</strong></div></article>`
  }
  const doctors = escapeHtml(slot.doctors.join(' · ') || slot.raw)
  const meta = []
  if (slot.remaining) meta.push(`余号 ${escapeHtml(slot.remaining)}`)
  if (slot.fee) meta.push(`¥${escapeHtml(formatFee(slot.fee))}`)
  const period = slot.period
    ? `<span class="chat-slot__period">${escapeHtml(slot.period)}</span>`
    : ''
  const metaHtml = meta.length ? `<span class="chat-slot__meta">${meta.join(' · ')}</span>` : ''
  return `<article class="chat-slot">${period}<div class="chat-slot__body"><strong>${doctors}</strong>${metaHtml}</div></article>`
}

export function enhanceAssistantHtml(html) {
  let next = String(html || '').replace(DAY_HTML, (_, _tag, label) => renderDay(label))
  next = next.replace(/<ul>([\s\S]*?)<\/ul>/gi, (full, inner) => {
    const items = [...inner.matchAll(/<li>([\s\S]*?)<\/li>/gi)].map((match) => stripTags(match[1]))
    if (!items.length) return full
    const parsed = items.map(parseSlotLine)
    const hits = parsed.filter(isScheduleSlot).length
    if (hits < Math.ceil(items.length / 2)) return full
    return `<div class="chat-slots">${parsed.map(renderSlot).join('')}</div>`
  })
  return next
}

function dayLabel(line) {
  const trimmed = String(line || '').trim()
  if (!trimmed || /^[-*]\s+/.test(trimmed)) return null
  const stripped = trimmed
    .replace(/^#{1,6}\s+/, '')
    .replace(/^\*{1,3}\s*|\s*\*{1,3}$/g, '')
    .trim()
  return DAY_LINE.test(stripped) ? stripped : null
}

export function normalizeScheduleMarkdown(text) {
  const out = []
  for (const line of String(text || '').split('\n')) {
    const label = dayLabel(line)
    if (label) {
      if (out.length && out[out.length - 1] !== '') out.push('')
      out.push(`### ${label}`)
      out.push('')
      continue
    }
    out.push(line)
  }
  return out.join('\n').replace(/\n{3,}/g, '\n\n')
}

export function renderAssistantMarkdown(markdown, { parse, sanitize }) {
  const cleaned = normalizeScheduleMarkdown(stripInternalIds(markdown))
  return sanitize(enhanceAssistantHtml(parse(cleaned)))
}
