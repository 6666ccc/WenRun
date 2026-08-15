export const DEFAULT_SESSION = { id: 'default', title: '新的问诊', messages: [] }

function isMessage(message) {
  return message && (message.role === 'user' || message.role === 'assistant') && typeof message.content === 'string'
}

function isSession(session) {
  return session && typeof session.id === 'string' && session.id && Array.isArray(session.messages)
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
      messages: session.messages.filter(isMessage),
    }))

  return sessions.length ? sessions : [{ ...DEFAULT_SESSION }]
}

export function createSession(id) {
  return { id, title: DEFAULT_SESSION.title, messages: [] }
}
