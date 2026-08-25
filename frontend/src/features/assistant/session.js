export const DEFAULT_SESSION = {
  id: 'default',
  title: '新的问诊',
  messages: [],
}

function isMessage(message) {
  return message && (message.role === 'user' || message.role === 'assistant') && typeof message.content === 'string'
}

function isSession(session) {
  return session && typeof session.id === 'string' && session.id && Array.isArray(session.messages)
}

export const createMessageId = () => `message_${Date.now()}_${Math.random().toString(16).slice(2)}`

function normalizeMessage(message, index) {
  return {
    id: typeof message.id === 'string' && message.id ? message.id : `legacy_${index}_${message.role}`,
    role: message.role,
    content: message.content,
    sources: Array.isArray(message.sources) ? message.sources : [],
    meta: message.meta && typeof message.meta === 'object' ? message.meta : { intent: null },
  }
}

export function normalizeSessions(raw) {
  let parsed
  try {
    parsed = typeof raw === 'string' ? JSON.parse(raw) : raw
  } catch {
    return [{ ...DEFAULT_SESSION }]
  }

  if (!Array.isArray(parsed)) return [{ ...DEFAULT_SESSION }]
  const sessions = parsed
    .filter(isSession)
    .map((session) => ({
      id: session.id,
      title: typeof session.title === 'string' && session.title ? session.title : DEFAULT_SESSION.title,
      messages: session.messages.filter(isMessage).map(normalizeMessage),
    }))

  return sessions.length ? sessions : [{ ...DEFAULT_SESSION }]
}

export function createSession(id) {
  return { id, title: DEFAULT_SESSION.title, messages: [] }
}

export function filterSessionsByTitle(sessions, query) {
  const list = Array.isArray(sessions) ? sessions : []
  const needle = String(query ?? '').trim().toLowerCase()
  if (!needle) return list.slice()
  return list.filter((session) => String(session.title ?? '').toLowerCase().includes(needle))
}

/** 服务端没有该会话、或只是本地残留时，允许清掉浏览器里的记录。 */
export function shouldRemoveLocalSessionAfterDeleteError(error, neverSynced) {
  if (!error || neverSynced) return true
  return String(error.message || '').includes('无权访问该会话')
}
