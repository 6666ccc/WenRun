import { computed, onMounted, ref, watch } from 'vue'
import { chatStream, deleteConversation, listCharges, listRegistrations } from '../api'
import { listVisits } from '../api/modules/consultation'
import {
  createMessageId,
  createRequestId,
  createSession,
  normalizeSessions,
  shouldRemoveLocalSessionAfterDeleteError,
} from '../features/assistant/session'
import { toTask } from '../features/assistant/task'

const STORAGE_KEY = 'wenrun_ai_sessions'
const FAST_MODE_KEY = 'wenrun_ai_fast_mode'
const LEGACY_OWNER_KEY = 'wenrun_ai_sessions_owner'
const makeId = () => `session_${Date.now()}_${Math.random().toString(16).slice(2)}`
const fulfilled = (result) => result.status === 'fulfilled' && Array.isArray(result.value) ? result.value : []
const runtimes = new Map()

function runtimeKey(user) {
  return String(user?.value?.userId || user?.value?.patientId || 'anonymous')
}

function scopedStorageKey(key) {
  return `${STORAGE_KEY}:${key}`
}

function scopedFastModeKey(key) {
  return `${FAST_MODE_KEY}:${key}`
}

function readFastMode(key) {
  return localStorage.getItem(scopedFastModeKey(key)) === 'true'
}

function readSessions(key) {
  try {
    const scoped = localStorage.getItem(scopedStorageKey(key))
    if (scoped) return normalizeSessions(scoped)
    // 兼容升级前的单用户存储；迁移后新写入只使用按用户隔离的键。
    const owner = localStorage.getItem(LEGACY_OWNER_KEY)
    if (owner && owner !== key) return normalizeSessions(null)
    const legacy = localStorage.getItem(STORAGE_KEY)
    if (legacy) {
      localStorage.setItem(LEGACY_OWNER_KEY, key)
      localStorage.setItem(scopedStorageKey(key), legacy)
    }
    return normalizeSessions(legacy)
  } catch {
    return normalizeSessions(null)
  }
}

function createRuntime(key) {
  const sessions = ref(readSessions(key))
  const activeId = ref(sessions.value[0]?.id || 'default')
  const context = ref({ appointments: [], charges: [], visits: [], loading: true, errors: {} })
  const replying = ref(false)
  const streaming = ref(false)
  const streamStatus = ref(null)
  const sessionError = ref(null)
  const fastMode = ref(readFastMode(key))
  const task = ref(null)
  const activeRequestId = ref(null)
  const requests = new Map()
  let contextPromise = null
  let destroyed = false

  watch(sessions, (value) => {
    if (!destroyed) {
      localStorage.setItem(scopedStorageKey(key), JSON.stringify(value))
    }
  }, { deep: true })

  watch(fastMode, (value) => {
    if (!destroyed) {
      localStorage.setItem(scopedFastModeKey(key), String(value))
    }
  })

  return {
    key,
    sessions,
    activeId,
    context,
    replying,
    streaming,
    streamStatus,
    sessionError,
    fastMode,
    task,
    activeRequestId,
    requests,
    get destroyed() { return destroyed },
    destroy() {
      destroyed = true
      for (const request of requests.values()) {
        request.status = 'stopped'
        request.controller.abort()
      }
      requests.clear()
      activeRequestId.value = null
      replying.value = false
      streaming.value = false
      streamStatus.value = null
    },
    async refreshContext(user) {
      if (contextPromise) return contextPromise
      if (!user?.value?.userId && !user?.value?.patientId) {
        context.value = { appointments: [], charges: [], visits: [], loading: false, errors: {} }
        return context.value
      }
      context.value.loading = true
      contextPromise = Promise.allSettled([
        listRegistrations({ userId: user.value?.userId }),
        listCharges({ patientId: user.value?.patientId }),
        listVisits({ patientId: user.value?.patientId }),
      ]).then(([appointments, charges, visits]) => {
        context.value = {
          appointments: fulfilled(appointments),
          charges: fulfilled(charges).filter((item) => item.payStatus === 0),
          visits: fulfilled(visits),
          loading: false,
          errors: { appointments: appointments.status === 'rejected', charges: charges.status === 'rejected', visits: visits.status === 'rejected' },
        }
        return context.value
      }).finally(() => {
        contextPromise = null
      })
      return contextPromise
    },
  }
}

function getRuntime(user) {
  const key = runtimeKey(user)
  let runtime = runtimes.get(key)
  if (!runtime || runtime.destroyed) {
    runtime = createRuntime(key)
    runtimes.set(key, runtime)
  }
  return runtime
}

export function resetAssistantRuntime(key) {
  const runtime = runtimes.get(String(key))
  if (!runtime) return
  runtime.destroy()
  runtimes.delete(String(key))
}

export function resetAllAssistantRuntimes() {
  for (const runtime of runtimes.values()) runtime.destroy()
  runtimes.clear()
}

function updateSession(runtime, id, updater) {
  runtime.sessions.value = runtime.sessions.value.map((session) => session.id === id ? updater(session) : session)
}

function updateRequestUser(runtime, conversationId, requestId, updater) {
  updateSession(runtime, conversationId, (session) => ({
    ...session,
    messages: session.messages.map((message) => (
      message.role === 'user' && message.meta?.requestId === requestId ? updater(message) : message
    )),
  }))
}

function updateAssistant(runtime, conversationId, requestId, updater) {
  updateSession(runtime, conversationId, (session) => {
    const messages = [...session.messages]
    const index = messages.findIndex((message) => message.role === 'assistant' && message.meta?.requestId === requestId)
    if (index >= 0) {
      messages[index] = updater(messages[index])
    } else {
      messages.push(updater({
        id: createMessageId(),
        role: 'assistant',
        content: '',
        sources: [],
        meta: { requestId, status: 'streaming' },
      }))
    }
    return { ...session, messages }
  })
}

function setRequestStatus(runtime, conversationId, requestId, status) {
  updateRequestUser(runtime, conversationId, requestId, (message) => ({
    ...message,
    meta: { ...message.meta, requestId, status },
  }))
}

function appendAssistantToken(runtime, conversationId, requestId, chunk) {
  const request = runtime.requests.get(requestId)
  if (!request || request.status !== 'running') return
  runtime.streaming.value = true
  updateAssistant(runtime, conversationId, requestId, (message) => ({
    ...message,
    content: message.content + chunk,
    meta: { ...message.meta, requestId, status: 'streaming' },
  }))
}

function appendAssistantSource(runtime, conversationId, requestId, source) {
  const request = runtime.requests.get(requestId)
  if (!request || request.status !== 'running') return
  updateAssistant(runtime, conversationId, requestId, (message) => ({
    ...message,
    sources: [...(message.sources || []), source],
    meta: { ...message.meta, requestId, status: 'streaming' },
  }))
}

function finalizeAssistantMessage(runtime, conversationId, requestId, { reply, intent, sources }) {
  const request = runtime.requests.get(requestId)
  if (!request || request.status !== 'running') return
  request.status = 'completed'
  updateAssistant(runtime, conversationId, requestId, (message) => ({
    ...message,
    content: reply || message.content,
    sources: sources || message.sources || [],
    meta: { ...message.meta, requestId, status: 'completed', intent },
  }))
  setRequestStatus(runtime, conversationId, requestId, 'completed')
}

function appendAssistantError(runtime, conversationId, requestId, code, message, status = 'error') {
  const request = runtime.requests.get(requestId)
  if (request && request.status === 'running') request.status = status
  updateAssistant(runtime, conversationId, requestId, (current) => ({
    ...current,
    content: message || 'AI 服务暂时不可用，请稍后重试。',
    meta: { ...current.meta, requestId, status, errorCode: code },
  }))
  setRequestStatus(runtime, conversationId, requestId, status)
}

function createStreamHandlers(runtime, conversationId, requestId) {
  return {
    signal: runtime.requests.get(requestId)?.controller.signal,
    onStatus: (text) => {
      if (runtime.requests.get(requestId)?.status === 'running') runtime.streamStatus.value = text
    },
    onToken: (chunk) => appendAssistantToken(runtime, conversationId, requestId, chunk),
    onCitation: (source) => appendAssistantSource(runtime, conversationId, requestId, source),
    onDone: (result) => finalizeAssistantMessage(runtime, conversationId, requestId, result),
    onError: ({ code, message }) => appendAssistantError(runtime, conversationId, requestId, code, message),
  }
}

export function useAssistant(user) {
  const runtime = getRuntime(user)
  const activeSession = computed(() => runtime.sessions.value.find((item) => item.id === runtime.activeId.value) || runtime.sessions.value[0])

  function newChat() {
    const next = createSession(makeId())
    runtime.sessions.value.push(next)
    runtime.activeId.value = next.id
  }

  async function deleteSession(id) {
    if (runtime.sessions.value.length <= 1) return
    runtime.sessionError.value = null
    const target = runtime.sessions.value.find((session) => session.id === id)
    const neverSynced = !target?.messages?.length
    try {
      await deleteConversation(id)
    } catch (error) {
      if (!shouldRemoveLocalSessionAfterDeleteError(error, neverSynced)) {
        runtime.sessionError.value = error.message || '删除会话失败，请重试。'
        return
      }
    }
    runtime.sessions.value = runtime.sessions.value.filter((session) => session.id !== id)
    if (runtime.activeId.value === id) runtime.activeId.value = runtime.sessions.value[0].id
  }

  async function sendMessage(text) {
    const content = text.trim()
    if (!content || runtime.activeRequestId.value || !activeSession.value) return
    const conversationId = activeSession.value.id
    const requestId = createRequestId()
    updateSession(runtime, conversationId, (session) => ({
      ...session,
      title: session.messages.length ? session.title : content.slice(0, 18),
      messages: [...session.messages, {
        id: createMessageId(),
        role: 'user',
        content,
        sources: [],
        meta: { requestId, status: 'pending' },
      }],
    }))
    const controller = new AbortController()
    runtime.requests.set(requestId, { conversationId, controller, status: 'running' })
    runtime.activeRequestId.value = requestId
    runtime.replying.value = true
    runtime.streaming.value = false
    runtime.streamStatus.value = null
    try {
      await chatStream(
        { message: content, conversationId, clientRequestId: requestId, fastMode: runtime.fastMode.value },
        createStreamHandlers(runtime, conversationId, requestId),
      )
    } catch (nextError) {
      const request = runtime.requests.get(requestId)
      if (nextError.name === 'AbortError' && request?.status === 'stopped') return
      if (request?.status === 'running') {
        appendAssistantError(runtime, conversationId, requestId, nextError.code, `暂时没有连接上医院智能体。${nextError.message || '请稍后重试。'}`)
      }
    } finally {
      runtime.requests.delete(requestId)
      if (runtime.activeRequestId.value === requestId) {
        runtime.activeRequestId.value = null
        runtime.replying.value = false
        runtime.streaming.value = false
        runtime.streamStatus.value = null
      }
    }
  }

  function stopRequest(requestId = runtime.activeRequestId.value) {
    if (!requestId) return
    const request = runtime.requests.get(requestId)
    if (!request || request.status !== 'running') return
    request.status = 'stopped'
    appendAssistantError(runtime, request.conversationId, requestId, 'AI_STREAM_STOPPED', '已停止生成。', 'stopped')
    runtime.activeRequestId.value = null
    runtime.replying.value = false
    runtime.streaming.value = false
    runtime.streamStatus.value = null
    request.controller.abort()
  }

  onMounted(() => runtime.refreshContext(user))

  return {
    sessions: runtime.sessions,
    activeId: runtime.activeId,
    activeSession,
    context: runtime.context,
    replying: runtime.replying,
    streaming: runtime.streaming,
    streamStatus: runtime.streamStatus,
    sessionError: runtime.sessionError,
    fastMode: runtime.fastMode,
    toggleFastMode: () => { runtime.fastMode.value = !runtime.fastMode.value },
    task: runtime.task,
    sendMessage,
    stopReply: () => stopRequest(),
    newChat,
    deleteSession,
    refreshContext: () => runtime.refreshContext(user),
    openTask: (value) => { runtime.task.value = toTask(value) },
    closeTask: () => { runtime.task.value = null },
  }
}
