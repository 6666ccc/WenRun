import { toTask } from '../../features/assistant/task.js'

export function normalizeChatEvent(event) {
  return event
}

export function taskFromChatEvent(event) {
  return toTask(event?.task)
}

/**
 * 流式 AI 对话（SSE）。
 * @param {{ message: string, conversationId?: string }} payload
 * @param {{ onEvent?: (event) => void, onToken?: (chunk) => void, onDone?: (reply) => void, signal?: AbortSignal }} handlers
 */
export async function chatStream(payload, handlers = {}) {
  const { onEvent, onToken, onDone, signal } = handlers
  const headers = { 'Content-Type': 'application/json', Accept: 'text/event-stream' }
  const { getToken } = await import('../request.js')
  const token = getToken()
  if (token) {
    headers.Authorization = `Bearer ${token}`
    headers['X-Token'] = token
  }

  const res = await fetch('/api/ai/chat/stream', {
    method: 'POST',
    headers,
    body: JSON.stringify(payload),
    signal,
  })

  if (!res.ok) {
    let message = `服务器错误 (${res.status})`
    try {
      const body = await res.json()
      message = body?.message || message
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
  let fullReply = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const parts = buffer.split('\n\n')
    buffer = parts.pop() || ''

    for (const part of parts) {
      const line = part
        .split('\n')
        .map((l) => l.trim())
        .find((l) => l.startsWith('data:'))
      if (!line) continue

      const raw = line.slice(5).trim()
      if (!raw) continue

      let event
      try {
        event = JSON.parse(raw)
      } catch {
        continue
      }

      event = normalizeChatEvent(event)
      onEvent?.(event)

      if (event.type === 'error') {
        throw new Error(event.content || 'AI 服务异常')
      }
      if (event.type === 'token' && event.content) {
        fullReply += event.content
        onToken?.(event.content)
      }
      if (event.type === 'done') {
        const reply = event.reply || fullReply
        onDone?.(reply)
        return reply
      }
    }
  }

  if (fullReply) {
    onDone?.(fullReply)
    return fullReply
  }

  throw new Error('流式响应意外结束')
}

/** 非流式对话（保留兼容） */
export async function chat(message) {
  const { default: request } = await import('../request')
  return request.post('/api/ai/chat', { message })
}
