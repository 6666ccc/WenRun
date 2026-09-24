export const ARCHIVE_TABS = ['health', 'trend', 'activity', 'documents', 'registrations']
export const ARCHIVE_DIALOGS = ['basic', 'history']

export function archiveTabFromQuery(tab) {
  if (ARCHIVE_DIALOGS.includes(tab)) return 'health'
  return ARCHIVE_TABS.includes(tab) ? tab : 'health'
}

export function archiveDialogFromQuery(tab) {
  return ARCHIVE_DIALOGS.includes(tab) ? tab : ''
}

export function calcAge(birthDate, now = new Date()) {
  if (!birthDate) return ''
  const birth = new Date(birthDate)
  if (Number.isNaN(birth.getTime())) return ''
  let age = now.getFullYear() - birth.getFullYear()
  const month = now.getMonth() - birth.getMonth()
  if (month < 0 || (month === 0 && now.getDate() < birth.getDate())) age -= 1
  return age >= 0 ? String(age) : ''
}

export function maskIdCard(value) {
  if (!value) return '—'
  if (value.length <= 8) return `${value.slice(0, 2)}••••${value.slice(-2)}`
  return `${value.slice(0, 4)} •••••• ${value.slice(-4)}`
}
