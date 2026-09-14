export const DEFAULT_SESSION_TITLE = '新的问诊'
const SESSION_STORAGE_KEY = 'wenrun_ai_sessions'
const SESSION_OWNER_KEY = 'wenrun_ai_sessions_owner'

export function createSessionId() {
  return `session_${Date.now()}_${Math.random().toString(16).slice(2)}`
}

function isMessage(message) {
  return message && (message.role === 'user' || message.role === 'assistant') && typeof message.content === 'string'
}

function isSession(session) {
  return session && typeof session.id === 'string' && session.id && Array.isArray(session.messages)
}

export const createMessageId = () => `message_${Date.now()}_${Math.random().toString(16).slice(2)}`
export const createRequestId = () => `request_${Date.now()}_${Math.random().toString(16).slice(2)}`

const MESSAGE_STATUSES = new Set(['pending', 'streaming', 'completed', 'error', 'stopped', 'confirming'])

function normalizeMessage(message, index) {
  const rawMeta = message.meta && typeof message.meta === 'object' ? message.meta : {}
  const status = MESSAGE_STATUSES.has(rawMeta.status) ? rawMeta.status : 'completed'
  return {
    id: typeof message.id === 'string' && message.id ? message.id : `legacy_${index}_${message.role}`,
    role: message.role,
    content: message.content,
    sources: Array.isArray(message.sources) ? message.sources : [],
    meta: { ...rawMeta, status },
  }
}

function uniqueSessionId(id) {
  if (typeof id === 'string' && id && id !== 'default') return id
  return createSessionId()
}

export function createSession(id = createSessionId()) {
  return { id: uniqueSessionId(id), title: DEFAULT_SESSION_TITLE, messages: [] }
}

export function normalizeSessions(raw) {
  let parsed
  try {
    parsed = typeof raw === 'string' ? JSON.parse(raw) : raw
  } catch {
    return [createSession()]
  }

  if (!Array.isArray(parsed)) return [createSession()]
  const sessions = parsed
    .filter(isSession)
    .map((session) => ({
      id: uniqueSessionId(session.id),
      title: typeof session.title === 'string' && session.title ? session.title : DEFAULT_SESSION_TITLE,
      messages: session.messages.filter(isMessage).map(normalizeMessage),
    }))

  return sessions.length ? sessions : [createSession()]
}

/** Read upgrade-only browser history without crossing the recorded account boundary. */
export function readOwnedLegacySessions(storage, ownerKey) {
  try {
    const scoped = storage.getItem(`${SESSION_STORAGE_KEY}:${ownerKey}`)
    if (scoped) return normalizeSessions(scoped)
    const recordedOwner = storage.getItem(SESSION_OWNER_KEY)
    if (recordedOwner && recordedOwner !== ownerKey) return normalizeSessions(null)
    const legacy = storage.getItem(SESSION_STORAGE_KEY)
    if (legacy) storage.setItem(SESSION_OWNER_KEY, ownerKey)
    return normalizeSessions(legacy)
  } catch {
    return normalizeSessions(null)
  }
}

export function clearLegacySessions(storage) {
  for (const key of Object.keys(storage)) {
    if (key === SESSION_STORAGE_KEY || key.startsWith(`${SESSION_STORAGE_KEY}:`)) {
      storage.removeItem(key)
    }
  }
  storage.removeItem(SESSION_OWNER_KEY)
}

export function normalizeServerMessages(messages) {
  if (!Array.isArray(messages)) return []
  return messages.filter(isMessage).map((message, index) => normalizeMessage({
    id: message.id == null ? undefined : `server_${message.id}`,
    role: message.role,
    content: message.content,
    sources: [],
    meta: {
      requestId: message.clientRequestId || undefined,
      status: 'completed',
      createTime: message.createTime,
      ...(message.metadata || {}),
    },
  }, index))
}

export function normalizeServerConversations(conversations, messagesById = {}) {
  if (!Array.isArray(conversations)) return []
  return conversations
    .filter((item) => item && typeof item.conversationId === 'string' && item.conversationId)
    .map((item) => ({
      id: item.conversationId,
      title: typeof item.title === 'string' && item.title ? item.title : DEFAULT_SESSION_TITLE,
      messages: normalizeServerMessages(messagesById[item.conversationId]),
      meta: { source: 'server', updateTime: item.updateTime, messageCount: item.messageCount || 0 },
    }))
}

export function sessionHasPendingConfirm(session) {
  return Boolean(session?.messages?.some((message) => (
    message?.role === 'assistant' && message?.meta?.confirm
  )))
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
