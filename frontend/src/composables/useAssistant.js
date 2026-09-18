import { computed, onMounted, ref, watch } from 'vue'
import {
  chatResume,
  chatStream,
  deleteConversation,
  listAiConversationMessages,
  listAiConversations,
  listRegistrations,
} from '../api'
import {
  createMessageId,
  createRequestId,
  createSession,
  createSessionId,
  clearLegacySessions,
  normalizeServerConversations,
  readOwnedLegacySessions,
  sessionHasPendingConfirm,
  shouldRemoveLocalSessionAfterDeleteError,
} from '../features/assistant/session'
import { toTask } from '../features/assistant/task'

const FAST_MODE_KEY = 'wenrun_ai_fast_mode'
const ACTIVE_ID_KEY = 'wenrun_ai_active_conversation'
const fulfilled = (result) => result.status === 'fulfilled' && Array.isArray(result.value) ? result.value : []
const runtimes = new Map()

function runtimeKey(user) {
  return String(user?.value?.userId || user?.value?.patientId || 'anonymous')
}

function scopedFastModeKey(key) {
  return `${FAST_MODE_KEY}:${key}`
}

function scopedActiveIdKey(key) {
  return `${ACTIVE_ID_KEY}:${key}`
}

function readFastMode(key) {
  return localStorage.getItem(scopedFastModeKey(key)) === 'true'
}

function readSessions(key) {
  return readOwnedLegacySessions(localStorage, key)
}

function createRuntime(key) {
  const sessions = ref(readSessions(key))
  const savedActiveId = localStorage.getItem(scopedActiveIdKey(key))
  const activeId = ref(savedActiveId || sessions.value[0]?.id || createSessionId())
  const context = ref({ appointments: [], loading: true, errors: {} })
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

  watch(activeId, (value) => {
    if (!destroyed && value) localStorage.setItem(scopedActiveIdKey(key), value)
  })

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
        context.value = { appointments: [], loading: false, errors: {} }
        return context.value
      }
      context.value.loading = true
      contextPromise = Promise.allSettled([
        listRegistrations({ userId: user.value?.userId }),
      ]).then(([appointments]) => {
        context.value = {
          appointments: fulfilled(appointments),
          loading: false,
          errors: { appointments: appointments.status === 'rejected' },
        }
        return context.value
      }).finally(() => {
        contextPromise = null
      })
      return contextPromise
    },
    async hydrateSessions() {
      try {
        const summaries = await listAiConversations({ page: 0, size: 30 })
        const messages = await Promise.all((summaries || []).map(async (summary) => [
          summary.conversationId,
          await listAiConversationMessages(summary.conversationId, { page: 0, size: 100 }),
        ]))
        const serverSessions = normalizeServerConversations(summaries, Object.fromEntries(messages))
        const serverIds = new Set(serverSessions.map((session) => session.id))
        const unsyncedLegacy = sessions.value.filter((session) => !serverIds.has(session.id))
        sessions.value = [...serverSessions, ...unsyncedLegacy]
        if (!sessions.value.length) sessions.value = [createSession()]
        if (!sessions.value.some((session) => session.id === activeId.value)) {
          activeId.value = sessions.value[0].id
        }
        clearLegacySessions(localStorage)
      } catch (error) {
        sessionError.value = error.message || '加载历史会话失败，本次仍可继续聊天。'
      }
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
  for (const key of Object.keys(localStorage)) {
    if (key.startsWith('wenrun_ai_')) localStorage.removeItem(key)
  }
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

function markAssistantAwaitingConfirm(runtime, conversationId, requestId, confirming) {
  const request = runtime.requests.get(requestId)
  if (request?.status === 'stopped') return
  if (request) request.status = 'confirming'
  updateAssistant(runtime, conversationId, requestId, (message) => ({
    ...message,
    content: message.content?.trim() ? message.content : (confirming.prompt || ''),
    meta: { ...message.meta, requestId, status: 'confirming', confirm: confirming },
  }))
}

function createStreamHandlers(runtime, conversationId, requestId) {
  return {
    signal: runtime.requests.get(requestId)?.controller.signal,
    onStatus: (text) => {
      if (runtime.requests.get(requestId)?.status === 'running') runtime.streamStatus.value = text
    },
    onToken: (chunk) => appendAssistantToken(runtime, conversationId, requestId, chunk),
    onCitation: (source) => appendAssistantSource(runtime, conversationId, requestId, source),
    onConfirm: (confirming) => markAssistantAwaitingConfirm(runtime, conversationId, requestId, confirming),
    onDone: (result) => finalizeAssistantMessage(runtime, conversationId, requestId, result),
    onError: ({ code, message }) => appendAssistantError(runtime, conversationId, requestId, code, message),
  }
}

export function useAssistant(user) {
  const runtime = getRuntime(user)
  const activeSession = computed(() => runtime.sessions.value.find((item) => item.id === runtime.activeId.value) || runtime.sessions.value[0])

  const awaitingConfirm = computed(() => sessionHasPendingConfirm(activeSession.value))

  function newChat() {
    const next = createSession()
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
      messages: [
        ...session.messages.map((item) => (
          item.meta?.confirm
            ? { ...item, meta: { ...item.meta, status: item.meta.status === 'confirming' ? 'completed' : item.meta.status, confirm: null } }
            : item
        )),
        {
          id: createMessageId(),
          role: 'user',
          content,
          sources: [],
          meta: { requestId, status: 'pending' },
        },
      ],
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

  async function respondToPending(message, decision) {
    const conversationId = message.meta?.confirm?.conversationId || runtime.activeId.value
    const interruptId = message.meta?.confirm?.interruptId
    const requestId = createRequestId()
    // 确认卡片一旦作答就不再可点，避免重复提交。
    updateSession(runtime, conversationId, (session) => ({
      ...session,
      messages: session.messages.map((item) => (
        item.id === message.id
          ? { ...item, meta: { ...item.meta, status: 'completed', confirm: null } }
          : item
      )),
    }))
    const controller = new AbortController()
    runtime.requests.set(requestId, { conversationId, controller, status: 'running' })
    runtime.activeRequestId.value = requestId
    runtime.replying.value = true
    runtime.streaming.value = false
    runtime.streamStatus.value = null
    try {
      await chatResume(
        {
          conversationId,
          decision,
          clientRequestId: requestId,
          interruptId,
        },
        createStreamHandlers(runtime, conversationId, requestId),
      )
    } catch (nextError) {
      const request = runtime.requests.get(requestId)
      if (nextError.name === 'AbortError' && request?.status === 'stopped') return
      if (request?.status === 'running') {
        appendAssistantError(runtime, conversationId, requestId, nextError.code, nextError.message)
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

  onMounted(() => {
    runtime.refreshContext(user)
    runtime.hydrateSessions()
  })

  return {
    sessions: runtime.sessions,
    activeId: runtime.activeId,
    activeSession,
    context: runtime.context,
    replying: runtime.replying,
    awaitingConfirm,
    streaming: runtime.streaming,
    streamStatus: runtime.streamStatus,
    sessionError: runtime.sessionError,
    fastMode: runtime.fastMode,
    toggleFastMode: () => { runtime.fastMode.value = !runtime.fastMode.value },
    task: runtime.task,
    sendMessage,
    stopReply: () => stopRequest(),
    confirmPending: (message) => respondToPending(message, 'approve'),
    rejectPending: (message) => respondToPending(message, 'reject'),
    newChat,
    deleteSession,
    refreshContext: () => runtime.refreshContext(user),
    openTask: (value) => { runtime.task.value = toTask(value) },
    closeTask: () => { runtime.task.value = null },
  }
}
