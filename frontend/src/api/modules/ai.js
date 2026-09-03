const API_BASE_URL = (import.meta.env?.VITE_API_BASE_URL || '').replace(/\/+$/, '')

function apiUrl(path) {
  return `${API_BASE_URL}${path}`
}

export function normalizeChatEvent(event) {
  return event
}

function applyChatEvent(raw, acc, handlers) {
  const event = normalizeChatEvent(raw)
  if (event.type === 'status') {
    handlers.onStatus?.(event.content)
    return null
  }
  if (event.type === 'token' && event.content) {
    acc.reply += event.content
    handlers.onToken?.(event.content)
    return null
  }
  if (event.type === 'citation') {
    const incoming = Array.isArray(event.sources) && event.sources.length ? event.sources : [event]
    for (const source of incoming) {
      acc.sources.push(source)
      handlers.onCitation?.(source)
    }
    return null
  }
  if (event.type === 'confirm') {
    const confirming = {
      kind: event.kind,
      prompt: event.prompt || '请确认是否继续办理',
      detail: event.detail || {},
      conversationId: event.conversationId,
    }
    handlers.onConfirm?.(confirming)
    return { status: 'confirming', ...confirming }
  }
  if (event.type === 'done') {
    const done = {
      reply: event.reply || event.content || acc.reply,
      intent: event.intent || acc.intent,
      sources: event.sources || acc.sources,
    }
    handlers.onDone?.(done)
    return { status: 'completed', ...done }
  }
  if (event.type === 'error') {
    const message = event.message || event.content || 'AI 服务异常'
    const error = { code: event.code, message }
    handlers.onError?.(error)
    const thrown = new Error(message)
    thrown.code = event.code
    throw thrown
  }
  return null
}

function finishStream(acc, handlers) {
  if (acc.reply) {
    const done = { reply: acc.reply, intent: acc.intent, sources: acc.sources }
    handlers.onDone?.(done)
    return { status: 'completed', ...done }
  }
  throw new Error('流式响应意外结束')
}

export async function consumeChatEvents(events, handlers = {}) {
  const acc = { reply: '', sources: [], intent: null }
  for (const raw of events) {
    const result = applyChatEvent(raw, acc, handlers)
    if (result) return result
  }
  return finishStream(acc, handlers)
}

function parseSseChunk(part, onEvent) {
  const line = part
    .split('\n')
    .map((item) => item.trim())
    .find((item) => item.startsWith('data:'))
  if (!line) return
  const raw = line.slice(5).trim()
  if (!raw) return
  try {
    onEvent(JSON.parse(raw))
  } catch {
    // ignore malformed SSE payloads
  }
}

async function streamRequest(url, payload, handlers = {}) {
  const { signal } = handlers
  const headers = { 'Content-Type': 'application/json', Accept: 'text/event-stream' }
  const { getToken } = await import('../request.js')
  const token = getToken()
  if (token) {
    headers.Authorization = `Bearer ${token}`
    headers['X-Token'] = token
  }

  const res = await fetch(url, {
    method: 'POST',
    headers,
    body: JSON.stringify(payload),
    signal,
  })

  const responseType = res.headers.get('content-type') || ''
  if (!res.ok || !responseType.includes('text/event-stream')) {
    let message = `服务器错误 (${res.status})`
    try {
      const body = await res.json()
      message = body?.message || message
      if (body?.code === 401) {
        const { setToken } = await import('../request.js')
        setToken(null)
        localStorage.removeItem('wenrun_user')
        if (typeof window !== 'undefined' && window.location.pathname !== '/login') {
          window.location.href = '/login'
        }
      }
    } catch {
      // ignore non-json error body
    }
    throw new Error(message)
  }

  const reader = res.body?.getReader()
  if (!reader) {
    throw new Error('浏览器不支持流式响应')
  }

  const decoder = new TextDecoder()
  let buffer = ''
  const acc = { reply: '', sources: [], intent: null }
  let terminal = null

  const handleEvent = (event) => {
    if (terminal) return
    terminal = applyChatEvent(event, acc, handlers)
  }

  while (!terminal) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const parts = buffer.split('\n\n')
    buffer = parts.pop() || ''
    for (const part of parts) {
      parseSseChunk(part, handleEvent)
      if (terminal) break
    }
  }
  if (!terminal && buffer.trim()) {
    parseSseChunk(buffer, handleEvent)
  }
  if (terminal) return terminal
  return finishStream(acc, handlers)
}

export function chatStream(payload, handlers = {}) {
  return streamRequest(apiUrl('/api/ai/chat/stream'), payload, handlers)
}

export function chatResume(payload, handlers = {}) {
  return streamRequest(apiUrl('/api/ai/chat/resume'), payload, handlers)
}

export async function deleteConversation(conversationId) {
  const { default: request } = await import('../request.js')
  return request.delete(`/api/ai/conversations/${encodeURIComponent(conversationId)}`)
}
