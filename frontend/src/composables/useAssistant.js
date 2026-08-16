import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { chatStream, deleteConversation, listCharges, listRegistrations, resumeStream } from '../api'
import { listVisits } from '../api/modules/consultation'
import { taskFromChatEvent } from '../api/modules/ai'
import { buildResumePayload } from '../features/assistant/interrupt'
import { createSession, normalizeSessions } from '../features/assistant/session'
import { toTask } from '../features/assistant/task'

const STORAGE_KEY = 'wenrun_ai_sessions'
const makeId = () => `session_${Date.now()}_${Math.random().toString(16).slice(2)}`
const fulfilled = (result) => result.status === 'fulfilled' && Array.isArray(result.value) ? result.value : []

export function useAssistant(user) {
  const sessions = ref(normalizeSessions(localStorage.getItem(STORAGE_KEY)))
  const activeId = ref(sessions.value[0]?.id || 'default')
  const context = ref({ appointments: [], charges: [], visits: [], loading: true, errors: {} })
  const replying = ref(false)
  const streaming = ref(false)
  const streamStatus = ref(null)
  const sessionError = ref(null)
  const task = ref(null)
  let controller = null
  const activeSession = computed(() => sessions.value.find((item) => item.id === activeId.value) || sessions.value[0])
  const pendingInterrupt = computed(() => activeSession.value?.pendingInterrupt || null)
  watch(sessions, (value) => localStorage.setItem(STORAGE_KEY, JSON.stringify(value)), { deep: true })

  async function refreshContext() {
    if (!user.value?.userId && !user.value?.patientId) return void (context.value = { appointments: [], charges: [], visits: [], loading: false, errors: {} })
    context.value.loading = true
    const [appointments, charges, visits] = await Promise.allSettled([
      listRegistrations({ userId: user.value?.userId }),
      listCharges({ patientId: user.value?.patientId }),
      listVisits({ patientId: user.value?.patientId }),
    ])
    context.value = {
      appointments: fulfilled(appointments),
      charges: fulfilled(charges).filter((item) => item.payStatus === 0),
      visits: fulfilled(visits),
      loading: false,
      errors: { appointments: appointments.status === 'rejected', charges: charges.status === 'rejected', visits: visits.status === 'rejected' },
    }
  }
  onMounted(refreshContext)
  onBeforeUnmount(() => controller?.abort())

  function updateSession(id, updater) {
    sessions.value = sessions.value.map((session) => session.id === id ? updater(session) : session)
  }
  function newChat() {
    const next = createSession(makeId())
    sessions.value.push(next)
    activeId.value = next.id
  }
  async function deleteSession(id) {
    if (sessions.value.length <= 1) return
    sessionError.value = null
    const target = sessions.value.find((session) => session.id === id)
    const neverSynced = !target?.messages?.length
    try {
      await deleteConversation(id)
    } catch (error) {
      if (!neverSynced) {
        sessionError.value = error.message || '删除会话失败，请重试。'
        return
      }
    }
    sessions.value = sessions.value.filter((session) => session.id !== id)
    if (activeId.value === id) activeId.value = sessions.value[0].id
  }

  function updateLastAssistant(conversationId, updater) {
    updateSession(conversationId, (session) => {
      const messages = [...session.messages]
      const last = messages.at(-1)
      if (last?.role === 'assistant') {
        messages[messages.length - 1] = updater(last)
      } else {
        messages.push(updater({ role: 'assistant', content: '', sources: [], meta: {} }))
      }
      return { ...session, messages }
    })
  }

  function appendAssistantToken(conversationId, chunk) {
    streaming.value = true
    updateLastAssistant(conversationId, (message) => ({
      ...message,
      content: message.content + chunk,
    }))
  }

  function appendAssistantSource(conversationId, source) {
    updateLastAssistant(conversationId, (message) => ({
      ...message,
      sources: [...(message.sources || []), source],
    }))
  }

  function finalizeAssistantMessage(conversationId, { reply, intent, sources }) {
    updateLastAssistant(conversationId, (message) => ({
      ...message,
      content: reply || message.content,
      sources: sources || message.sources || [],
      meta: { ...message.meta, intent },
    }))
    updateSession(conversationId, (session) => ({
      ...session,
      pendingInterrupt: null,
    }))
  }

  function appendAssistantError(conversationId, code, message) {
    updateLastAssistant(conversationId, (current) => ({
      ...current,
      content: message || 'AI 服务暂时不可用，请稍后重试。',
      meta: { ...current.meta, errorCode: code },
    }))
  }

  function createStreamHandlers(conversationId) {
    return {
      signal: controller?.signal,
      onStatus: (text) => { streamStatus.value = text },
      onToken: (chunk) => appendAssistantToken(conversationId, chunk),
      onCitation: (source) => appendAssistantSource(conversationId, source),
      onInterrupt: (interrupt) => {
        updateLastAssistant(conversationId, (message) => ({
          ...message,
          content: message.content || interrupt?.summary || '请确认是否继续该操作。',
        }))
        updateSession(conversationId, (session) => ({
          ...session,
          pendingInterrupt: interrupt,
        }))
      },
      onDone: ({ reply, intent, sources }) => finalizeAssistantMessage(
        conversationId,
        { reply, intent, sources },
      ),
      onError: ({ code, message }) => appendAssistantError(
        conversationId,
        code,
        message,
      ),
      onEvent: (event) => {
        const next = taskFromChatEvent(event)
        if (next) task.value = next
      },
    }
  }

  async function sendMessage(text) {
    const content = text.trim()
    if (!content || replying.value || pendingInterrupt.value || !activeSession.value) return
    const conversationId = activeSession.value.id
    updateSession(conversationId, (session) => ({
      ...session,
      title: session.messages.length ? session.title : content.slice(0, 18),
      messages: [...session.messages, { role: 'user', content, sources: [], meta: {} }],
    }))
    controller = new AbortController()
    replying.value = true
    streaming.value = false
    streamStatus.value = null
    try {
      await chatStream({ message: content, conversationId }, createStreamHandlers(conversationId))
    } catch (nextError) {
      if (nextError.name !== 'AbortError') {
        appendAssistantError(conversationId, nextError.code, `暂时没有连接上医院智能体。${nextError.message || '请稍后重试。'}`)
      }
    } finally {
      replying.value = false
      streaming.value = false
      streamStatus.value = null
      controller = null
    }
  }

  async function resumeInterrupt(approved, params = {}) {
    const pending = pendingInterrupt.value
    const session = activeSession.value
    if (!pending || !session || replying.value) return
    controller = new AbortController()
    replying.value = true
    try {
      const result = await resumeStream(
        buildResumePayload(session.id, pending.interruptId, approved, params),
        createStreamHandlers(session.id),
      )
      if (approved && result?.status === 'completed') {
        await refreshContext()
      }
    } catch (nextError) {
      if (nextError.name !== 'AbortError') {
        appendAssistantError(session.id, nextError.code, nextError.message || '恢复对话失败，请稍后重试。')
      }
    } finally {
      replying.value = false
      streaming.value = false
      streamStatus.value = null
      controller = null
    }
  }

  return {
    sessions, activeId, activeSession, context, replying, streaming, streamStatus, pendingInterrupt, sessionError, task,
    sendMessage, resumeInterrupt, stopReply: () => controller?.abort(), newChat, deleteSession,
    refreshContext, openTask: (value) => { task.value = toTask(value) },
    closeTask: () => { task.value = null },
  }
}
