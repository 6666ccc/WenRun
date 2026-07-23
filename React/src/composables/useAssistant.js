import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { chatStream, listCharges, listRegistrations } from '../api'
import { listVisits } from '../api/modules/consultation'
import { createRegistration } from '../api/modules/registration'
import { taskFromChatEvent } from '../api/modules/ai'
import { createSession, normalizeSessions } from '../features/assistant/session'
import { toTask } from '../features/assistant/task'

const STORAGE_KEY = 'wenrun_ai_sessions'
const makeId = () => `session_${Date.now()}_${Math.random().toString(16).slice(2)}`
const fulfilled = (result) => result.status === 'fulfilled' && Array.isArray(result.value) ? result.value : []

export function useAssistant(user) {
  const sessions = ref(normalizeSessions(localStorage.getItem(STORAGE_KEY)))
  const activeId = ref(sessions.value[0]?.id || 'default')
  const context = ref({ appointments: [], charges: [], visits: [], loading: true, errors: {} })
  const replying = ref(false), streaming = ref(false), task = ref(null)
  let controller = null
  const activeSession = computed(() => sessions.value.find((item) => item.id === activeId.value) || sessions.value[0])
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
    sessions.value.push(next); activeId.value = next.id
  }
  function deleteSession(id) {
    if (sessions.value.length <= 1) return
    sessions.value = sessions.value.filter((session) => session.id !== id)
    if (activeId.value === id) activeId.value = sessions.value[0].id
  }
  async function sendMessage(text) {
    const content = text.trim()
    if (!content || replying.value || !activeSession.value) return
    const conversationId = activeSession.value.id
    updateSession(conversationId, (session) => ({ ...session, title: session.messages.length ? session.title : content.slice(0, 18), messages: [...session.messages, { role: 'user', content }] }))
    controller = new AbortController(); replying.value = true; streaming.value = false
    try {
      await chatStream({ message: content, conversationId }, {
        signal: controller.signal,
        onEvent: (event) => { const next = taskFromChatEvent(event); if (next) task.value = next },
        onToken: (chunk) => {
          streaming.value = true
          updateSession(conversationId, (session) => {
            const messages = [...session.messages], last = messages.at(-1)
            if (last?.role === 'assistant') messages[messages.length - 1] = { ...last, content: last.content + chunk }
            else messages.push({ role: 'assistant', content: chunk })
            return { ...session, messages }
          })
        },
        onDone: (reply) => updateSession(conversationId, (session) => {
          const messages = [...session.messages], last = messages.at(-1)
          if (last?.role === 'assistant') messages[messages.length - 1] = { ...last, content: reply || last.content }
          else if (reply) messages.push({ role: 'assistant', content: reply })
          return { ...session, messages }
        }),
      })
    } catch (nextError) {
      if (nextError.name !== 'AbortError') updateSession(conversationId, (session) => ({ ...session, messages: [...session.messages, { role: 'assistant', content: `暂时没有连接上医院智能体。${nextError.message || '请稍后重试。'}` }] }))
    } finally { replying.value = false; streaming.value = false; controller = null }
  }
  async function submitRegistration(scheduleId) {
    if (!user.value?.patientId || !scheduleId) throw new Error('请选择可预约的排班')
    await createRegistration({ patientId: user.value.patientId, scheduleId })
    await refreshContext()
  }
  return {
    sessions, activeId, activeSession, context, replying, streaming, task,
    sendMessage, stopReply: () => controller?.abort(), newChat, deleteSession,
    refreshContext, openTask: (value) => { task.value = toTask(value) },
    closeTask: () => { task.value = null }, submitRegistration,
  }
}
