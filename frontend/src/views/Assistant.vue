<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { useAuth } from '../stores'
import { useAssistant } from '../composables/useAssistant'
import { filterSessionsByTitle } from '../features/assistant/session'
import AssistantShell from '../components/AssistantShell.vue'
import UiIcon from '../components/UiIcon.vue'
import CitationList from '../components/CitationList.vue'

const router = useRouter()
const { user } = useAuth()
const assistant = useAssistant(user)
const input = ref('')
const query = ref('')
const end = ref(null)
const composer = ref(null)
const taskPanel = ref(null)
const shell = ref(null)
const copiedId = ref('')
const taskReturnFocus = ref(null)
let taskPreviousOverflow = ''
let copiedTimer
const suggestions = ['最近总是睡不好，挂什么科？', '查看我最近的预约', '我有待缴费用吗？', '如何查看就诊记录？']
const urgent = computed(() => /胸痛|呼吸困难|意识障碍|大量出血/.test([...assistant.activeSession.value?.messages || []].reverse().find((item) => item.role === 'user')?.content || ''))
const totalCharges = computed(() => assistant.context.value.charges.reduce((sum, item) => sum + Number(item.totalAmount || 0), 0))
const hasMessages = computed(() => Boolean(assistant.activeSession.value?.messages.length))
const visibleMessages = computed(() => (assistant.activeSession.value?.messages || []).filter((message) => (
  message.role === 'user' || message.content || message.meta?.status === 'error' || message.meta?.status === 'stopped'
)))
const visibleSessions = computed(() => filterSessionsByTitle(assistant.sessions.value, query.value))
const nextAppointment = computed(() => assistant.context.value.appointments[0])

watch(() => [assistant.activeSession.value?.messages.length, assistant.replying.value], async () => {
  await nextTick()
  const reduceMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
  end.value?.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'nearest' })
})

function send(text = input.value) {
  if (!text.trim() || assistant.replying.value) return
  assistant.sendMessage(text)
  input.value = ''
  nextTick(resetComposerHeight)
}

async function copyMessage(message) {
  try {
    await navigator.clipboard.writeText(message.content || '')
    copiedId.value = message.id
    clearTimeout(copiedTimer)
    copiedTimer = setTimeout(() => { copiedId.value = '' }, 1600)
  } catch {
    copiedId.value = ''
  }
}

const renderMarkdown = (value) => DOMPurify.sanitize(marked.parse(value || ''))

function keydown(event) {
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
    event.preventDefault()
    send()
  }
}

function openTask(task) {
  if (task.type === 'registration') router.push('/registration')
  else assistant.openTask(task)
}

function selectSession(id) {
  assistant.activeId.value = id
  shell.value?.closeHistory()
}

function newChat() {
  assistant.newChat()
  shell.value?.closeHistory()
}

function viewContext(task) {
  shell.value?.closeContext(false)
  openTask(task)
}

function contextText(kind, filled, empty) {
  if (assistant.context.value.errors[kind]) return '暂时无法获取'
  return filled || empty
}

function onTaskKeydown(event) {
  if (!assistant.task.value) return
  if (event.key === 'Escape') {
    event.preventDefault()
    assistant.closeTask()
    return
  }
  if (event.key !== 'Tab') return
  const focusable = [...taskPanel.value?.querySelectorAll('button:not([disabled]), [href], input, select, textarea') || []]
  if (!focusable.length) return
  const first = focusable[0]
  const last = focusable[focusable.length - 1]
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault()
    last.focus()
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault()
    first.focus()
  }
}

watch(() => assistant.task.value, (task) => {
  if (task) {
    taskReturnFocus.value = document.activeElement instanceof HTMLElement ? document.activeElement : null
    taskPreviousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    document.addEventListener('keydown', onTaskKeydown)
    nextTick(() => taskPanel.value?.querySelector('button:not([disabled]), [href], input, select, textarea')?.focus())
  } else {
    document.removeEventListener('keydown', onTaskKeydown)
    document.body.style.overflow = taskPreviousOverflow
    const target = taskReturnFocus.value
    taskReturnFocus.value = null
    nextTick(() => target?.isConnected && target.focus())
  }
})

function resetComposerHeight() {
  if (!composer.value) return
  composer.value.style.height = '28px'
  composer.value.style.overflowY = 'hidden'
}

function resizeComposer(event) {
  const textarea = event.target
  textarea.style.height = 'auto'
  const nextHeight = Math.min(textarea.scrollHeight, 200)
  textarea.style.height = `${Math.max(28, nextHeight)}px`
  textarea.style.overflowY = textarea.scrollHeight > 200 ? 'auto' : 'hidden'
}

onMounted(() => marked.setOptions({ breaks: true, gfm: true }))
onBeforeUnmount(() => {
  document.removeEventListener('keydown', onTaskKeydown)
  document.body.style.overflow = taskPreviousOverflow
  clearTimeout(copiedTimer)
})
</script>

<template>
  <AssistantShell ref="shell">
    <template #header-actions>
      <button class="chat-top-new" type="button" aria-label="开启新对话" @click="newChat">
        <UiIcon name="plus" :size="18" />
      </button>
    </template>

    <template #sidebar>
      <button class="chat-history-new" type="button" @click="newChat">
        <UiIcon name="plus" :size="17" />开启新对话
      </button>
      <label class="chat-history-search">
        <UiIcon name="search" :size="16" />
        <input v-model="query" type="search" placeholder="搜索会话" aria-label="搜索会话标题">
      </label>
      <div class="chat-history-list">
        <p class="chat-history-label">对话</p>
        <p v-if="!visibleSessions.length" class="chat-history-empty">没有匹配的会话</p>
        <div v-for="session in visibleSessions" :key="session.id" class="chat-history-item" :class="{ 'is-active': session.id === assistant.activeId.value }">
          <button type="button" @click="selectSession(session.id)">{{ session.title }}</button>
          <button v-if="assistant.sessions.value.length > 1" class="chat-history-item__delete" type="button" :aria-label="`删除会话：${session.title}`" @click="assistant.deleteSession(session.id)">×</button>
        </div>
      </div>
      <p v-if="assistant.sessionError.value" class="chat-history-error">{{ assistant.sessionError.value }}</p>
    </template>

    <template #context>
      <section class="chat-context-card">
        <small>下一次就诊</small>
        <strong>{{ contextText('appointments', nextAppointment ? `${nextAppointment.deptName} · ${nextAppointment.staffName}` : '', '还没有预约') }}</strong>
        <button type="button" @click="viewContext({ type: 'registration', title: '预约挂号' })">查看</button>
      </section>
      <section class="chat-context-card">
        <small>待缴费用</small>
        <strong>{{ contextText('charges', assistant.context.value.charges.length ? `¥${totalCharges.toFixed(2)}` : '', '暂无待缴账单') }}</strong>
        <button type="button" @click="viewContext({ type: 'payment', title: '待缴费用' })">查看</button>
      </section>
      <section class="chat-context-card">
        <small>最近就诊</small>
        <strong>{{ contextText('visits', assistant.context.value.visits.length ? `${assistant.context.value.visits.length} 条记录` : '', '暂无就诊记录') }}</strong>
        <button type="button" @click="viewContext({ type: 'records', title: '就诊记录' })">查看</button>
      </section>
    </template>

    <div class="chat-page">
      <main class="chat-main" aria-label="健康助手对话">
        <div v-if="urgent" class="chat-alerts">
          <div class="assistant-urgent" role="alert" aria-live="assertive"><strong>请优先处理急症</strong><span>前往急诊或拨打 120。</span></div>
        </div>

        <div v-if="!hasMessages" class="chat-empty">
          <span class="chat-empty__mark" aria-hidden="true"><UiIcon name="logo" :size="32" /></span>
          <h1>你好，我是温润健康助手。</h1>
        </div>

        <div v-else class="chat-thread" aria-live="polite">
          <TransitionGroup name="message-in" tag="div" class="chat-message-list">
            <article v-for="message in visibleMessages" :key="message.id" class="chat-message" :class="`chat-message--${message.role}`">
              <div v-if="message.role === 'user'" class="chat-message__user-content">{{ message.content }}</div>
              <div v-else class="chat-message__assistant-content">
                <div class="chat-md" v-html="renderMarkdown(message.content)" />
                <CitationList v-if="message.sources?.length" :sources="message.sources" />
                <button
                  v-if="message.content"
                  class="chat-message__copy"
                  type="button"
                  :aria-label="copiedId === message.id ? '已复制回复' : '复制回复'"
                  @click="copyMessage(message)"
                >
                  <UiIcon name="copy" :size="14" />
                  {{ copiedId === message.id ? '已复制' : '复制' }}
                </button>
              </div>
            </article>
          </TransitionGroup>
          <div v-if="assistant.replying.value && !assistant.streaming.value" class="chat-typing" aria-live="polite" aria-label="正在整理信息">
            <span /><span /><span />
          </div>
          <div ref="end" />
        </div>
      </main>

      <footer class="chat-composer-wrap">
        <div v-if="!hasMessages" class="chat-suggestions" aria-label="推荐问题">
          <button v-for="item in suggestions" :key="item" type="button" @click="send(item)">{{ item }}</button>
        </div>
        <div class="chat-composer">
          <textarea
            ref="composer"
            v-model="input"
            rows="1"
            :disabled="assistant.replying.value"
            placeholder="给健康助手发送消息"
            aria-label="输入健康问题"
            enterkeyhint="send"
            @input="resizeComposer"
            @keydown="keydown"
          />
          <div class="chat-composer__tools">
            <button class="chat-composer__chip" type="button" @click="openTask({ type: 'registration', title: '预约挂号' })">
              <UiIcon name="calendar" :size="15" />挂号
            </button>
            <button class="chat-composer__chip" type="button" @click="openTask({ type: 'payment', title: '待缴费用' })">
              <UiIcon name="wallet" :size="15" />待缴
            </button>
            <button class="chat-composer__chip" type="button" @click="openTask({ type: 'records', title: '就诊记录' })">
              <UiIcon name="record" :size="15" />记录
            </button>
          </div>
          <button v-if="assistant.replying.value" class="chat-composer__send is-stop" type="button" aria-label="停止生成" @click="assistant.stopReply">
            <UiIcon name="stop" :size="13" />
          </button>
          <button v-else class="chat-composer__send" type="button" :disabled="!input.trim()" aria-label="发送消息" @click="send()">
            <UiIcon name="arrowUp" :size="18" />
          </button>
        </div>
        <p class="chat-disclaimer">内容由 AI 生成，仅供健康参考，不替代医生诊断。</p>
      </footer>
    </div>
  </AssistantShell>

  <Teleport to="body">
    <Transition name="fade">
      <div v-if="assistant.task.value" class="assistant-task-overlay" role="presentation" @mousedown.self="assistant.closeTask">
        <section ref="taskPanel" class="assistant-task" role="dialog" aria-modal="true" :aria-label="assistant.task.value.title">
          <button class="icon-button assistant-task__close" type="button" aria-label="关闭" title="关闭" @click="assistant.closeTask">×</button>
          <p class="eyebrow">健康服务</p>
          <h2>{{ assistant.task.value.title }}</h2>
          <template v-if="assistant.task.value.type === 'payment'">
            <p>确认账单后将在安全支付页继续办理。</p>
            <div class="assistant-task__options">
              <button v-for="charge in assistant.context.value.charges" :key="charge.id" type="button" @click="router.push(`/payment/${charge.id}`);assistant.closeTask()">
                <span><strong>{{ charge.orderNo || '门诊费用' }}</strong><small>{{ charge.createTime || '待缴费' }}</small></span>
                <b>¥{{ Number(charge.totalAmount || 0).toFixed(2) }}</b>
              </button>
              <div v-if="!assistant.context.value.charges.length" class="assistant-task__empty">目前没有待缴账单。</div>
            </div>
          </template>
          <template v-else>
            <p>就诊记录保留在患者服务中，便于完整查看。</p>
            <div class="assistant-task__empty">你可以查看历史挂号、就诊信息和个人档案。</div>
            <button class="btn btn--primary btn--full" type="button" @click="router.push('/registration');assistant.closeTask()">查看就诊记录</button>
          </template>
        </section>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.chat-top-new {
  display: grid;
  place-items: center;
  width: 40px;
  height: 40px;
  border: 0;
  border-radius: 10px;
  background: transparent;
  color: var(--color-text-secondary);
  cursor: pointer;
}

.chat-top-new:hover,
.chat-top-new:focus-visible {
  background: rgba(16, 24, 32, .06);
  color: var(--color-text);
}

.chat-page {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.chat-main {
  width: min(768px, 100%);
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: auto;
  margin: 0 auto;
  padding: 8px 20px 8px;
}

.chat-alerts { width: 100%; padding: 4px 0 8px; }

.assistant-urgent {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 10px 14px;
  border: 1px solid #f1b8b3;
  border-radius: 12px;
  background: var(--color-danger-bg);
  color: var(--color-danger);
  font-size: 14px;
  line-height: 1.5;
}

.chat-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: 1;
  padding: 12px 12px 24px;
  text-align: center;
}

.chat-empty__mark {
  width: 64px;
  height: 64px;
  display: grid;
  place-items: center;
  margin-bottom: 20px;
  border-radius: 18px;
  background: var(--color-brand-800);
  color: #fff;
}

.chat-empty h1 {
  max-width: 18em;
  margin: 0;
  color: #1a1a1a;
  font-size: clamp(28px, 3.6vw, 36px);
  font-weight: 600;
  letter-spacing: -.04em;
  line-height: 1.3;
}

.chat-suggestions {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 8px;
  width: 100%;
  margin-bottom: 12px;
}

.chat-suggestions button {
  min-height: 36px;
  padding: 7px 14px;
  border: 1px solid #e5e7eb;
  border-radius: 999px;
  background: #fff;
  color: #334155;
  cursor: pointer;
  font: inherit;
  font-size: 13px;
}

.chat-suggestions button:hover,
.chat-suggestions button:focus-visible {
  border-color: #d1d5db;
  background: #f8faf9;
}

.chat-thread { padding: 8px 0 20px; }

.chat-message { margin: 0 0 22px; }

.chat-message--user {
  display: flex;
  justify-content: flex-end;
}

.chat-message__user-content {
  max-width: min(560px, 78%);
  padding: 10px 16px;
  border-radius: 18px;
  background: #f4f4f4;
  color: #1a1a1a;
  line-height: 1.65;
  overflow-wrap: anywhere;
}

.chat-message--assistant { max-width: 100%; }

.chat-message__assistant-content {
  color: #1a1a1a;
  font-size: 16px;
  line-height: 1.75;
}

.chat-message__assistant-content :deep(p) { margin: 0 0 10px; }
.chat-message__assistant-content :deep(p:last-child) { margin-bottom: 0; }
.chat-message__assistant-content :deep(ul),
.chat-message__assistant-content :deep(ol) { padding-left: 22px; }

.chat-message__copy {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 32px;
  margin-top: 8px;
  padding: 0 8px 0 6px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: #6b7280;
  cursor: pointer;
  font: inherit;
  font-size: 12px;
  opacity: 0;
}

.chat-message--assistant:hover .chat-message__copy,
.chat-message--assistant:focus-within .chat-message__copy,
.chat-message__copy:focus-visible {
  opacity: 1;
}

.chat-message__copy:hover,
.chat-message__copy:focus-visible {
  background: #f3f4f6;
  color: #111827;
}

.chat-typing {
  display: flex;
  align-items: center;
  gap: 6px;
  min-height: 28px;
}

.chat-typing span {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #8aa09c;
  animation: chat-dot 1.1s var(--ease-standard) infinite;
}

.chat-typing span:nth-child(2) { animation-delay: .16s; }
.chat-typing span:nth-child(3) { animation-delay: .32s; }

.chat-composer-wrap {
  width: min(768px, 100%);
  max-width: 100%;
  margin: 0 auto;
  padding: 8px 20px 12px;
  padding-bottom: max(12px, env(safe-area-inset-bottom));
  background: #fff;
}

.chat-composer {
  position: relative;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 32px;
  grid-template-areas:
    "input input"
    "tools send";
  align-items: end;
  column-gap: 8px;
  row-gap: 10px;
  padding: 16px 16px 12px;
  border: 1px solid #e5e7eb;
  border-radius: 28px;
  background: #fff;
  box-shadow: 0 4px 24px rgba(15, 23, 42, .04);
}

.chat-composer:focus-within {
  border-color: #d1d5db;
  box-shadow: 0 8px 28px rgba(15, 23, 42, .07);
}

.chat-composer textarea,
.chat-composer textarea:focus,
.chat-composer textarea:focus-visible {
  grid-area: input;
  width: 100%;
  min-height: 28px;
  max-height: 200px;
  padding: 2px 4px;
  resize: none;
  border: 0;
  outline: 0 !important;
  box-shadow: none !important;
  background: transparent;
  color: #1a1a1a;
  font: inherit;
  font-size: 16px;
  line-height: 1.6;
}

.chat-composer__tools {
  grid-area: tools;
  display: flex;
  min-width: 0;
  gap: 8px;
  overflow-x: auto;
  scrollbar-width: none;
}

.chat-composer__tools::-webkit-scrollbar { display: none; }

.chat-composer__chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 34px;
  padding: 0 12px;
  border: 1px solid #e5e7eb;
  border-radius: 999px;
  background: #fff;
  color: #4b5563;
  cursor: pointer;
  font: inherit;
  font-size: 13px;
  white-space: nowrap;
}

.chat-composer__chip:hover,
.chat-composer__chip:focus-visible {
  border-color: #d1d5db;
  background: #f9fafb;
  color: #111827;
}

.chat-composer__send {
  grid-area: send;
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  justify-self: end;
  border: 0;
  border-radius: 50%;
  background: var(--color-brand-700);
  color: #fff;
  cursor: pointer;
}

.chat-composer__send:not(:disabled):hover,
.chat-composer__send:not(:disabled):focus-visible {
  background: var(--color-brand-800);
}

.chat-composer__send:disabled {
  background: #9aa3ab;
  color: #fff;
  cursor: not-allowed;
}

.chat-composer__send.is-stop {
  background: var(--color-text);
}

.chat-composer__send.is-stop :deep(svg) {
  fill: currentColor;
  stroke: none;
}

.chat-disclaimer {
  margin: 10px 0 0;
  color: #9ca3af;
  font-size: 12px;
  text-align: center;
}

.chat-history-new {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 8px;
  width: 100%;
  min-height: 40px;
  margin: 0 0 8px;
  padding: 0 12px;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  background: #fff;
  color: #111827;
  cursor: pointer;
  font: inherit;
  font-size: 14px;
}

.chat-history-new:hover,
.chat-history-new:focus-visible {
  border-color: #d1d5db;
  background: #fff;
}

.chat-history-search {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 40px;
  margin: 0 0 12px;
  padding: 0 10px;
  border: 0;
  border-radius: 10px;
  background: #eceef1;
  color: #6b7280;
}

.chat-history-search input {
  width: 100%;
  border: 0;
  outline: 0;
  background: transparent;
  color: var(--color-text);
  font: inherit;
}

.chat-history-list {
  display: grid;
  gap: 2px;
}

.chat-history-label {
  margin: 4px 10px 6px;
  color: #9ca3af;
  font-size: 12px;
}

.chat-history-empty,
.chat-history-error { margin: 8px 4px 0; font-size: 13px; }
.chat-history-empty { color: var(--color-text-secondary); }
.chat-history-error { color: var(--color-danger); }

.chat-history-item {
  display: flex;
  align-items: center;
  border-radius: 10px;
}

.chat-history-item:hover:not(.is-active) { background: #f0f1f3; }
.chat-history-item.is-active { background: #eceef1; }

.chat-history-item > button:first-child {
  min-width: 0;
  flex: 1;
  padding: 9px 10px;
  overflow: hidden;
  border: 0;
  background: transparent;
  color: #111827;
  cursor: pointer;
  font: inherit;
  font-size: 14px;
  text-align: left;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chat-history-item__delete {
  width: 32px;
  height: 32px;
  margin-right: 4px;
  border: 0;
  background: transparent;
  color: var(--color-text-secondary);
  cursor: pointer;
  font-size: 18px;
  opacity: 0;
}

.chat-history-item:hover .chat-history-item__delete,
.chat-history-item:focus-within .chat-history-item__delete { opacity: 1; }

@media (pointer: coarse) {
  .chat-history-item__delete { opacity: 1; }
}

.chat-history-item__delete:hover { color: var(--color-danger); }

.chat-context-card { padding: 16px 0; border-bottom: 1px solid var(--color-border); }
.chat-context-card small,
.chat-context-card strong { display: block; }
.chat-context-card small { color: var(--color-text-secondary); font-size: 13px; }
.chat-context-card strong { margin: 7px 0 12px; }
.chat-context-card button {
  padding: 0;
  border: 0;
  background: none;
  color: var(--color-brand-700);
  cursor: pointer;
  font: inherit;
  font-size: 14px;
  font-weight: 650;
}

.icon-button {
  display: grid;
  place-items: center;
  width: 40px;
  height: 40px;
  border: 1px solid var(--color-border);
  border-radius: 9px;
  background: var(--color-surface);
  color: var(--color-text-secondary);
  cursor: pointer;
  font-size: 20px;
}

.assistant-task-overlay {
  position: fixed;
  inset: 0;
  z-index: 50;
  display: grid;
  place-items: center;
  padding: 20px;
  background: rgba(16, 42, 46, .4);
}

.assistant-task {
  position: relative;
  width: min(560px, 100%);
  max-height: 85vh;
  overflow: auto;
  padding: 28px;
  border-radius: 20px;
  background: #fff;
  box-shadow: 0 20px 48px rgba(16, 42, 46, .18);
}

.assistant-task__close { position: absolute; top: 18px; right: 18px; }
.assistant-task h2 { margin: 6px 0; }
.assistant-task > p { color: var(--color-text-secondary); }
.assistant-task__options { display: grid; gap: 8px; margin: 18px 0; }
.assistant-task__options button {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px;
  border: 1px solid var(--color-border);
  border-radius: 10px;
  background: #fff;
  color: var(--color-text);
  cursor: pointer;
  text-align: left;
}
.assistant-task__options strong,
.assistant-task__options small { display: block; }
.assistant-task__options small { margin-top: 3px; color: var(--color-text-secondary); }
.assistant-task__empty {
  padding: 18px;
  border-radius: 10px;
  background: var(--color-mint-050);
  color: var(--color-text-secondary);
  text-align: center;
}
.btn--full { width: 100%; }
.chat-message-list { display: block; }

.message-in-enter-active { transition: opacity var(--motion-med) var(--ease-enter), transform var(--motion-med) var(--ease-enter); }
.message-in-enter-from { opacity: 0; transform: translateY(4px); }
.message-in-leave-active { transition: opacity var(--motion-exit) var(--ease-exit); }
.message-in-leave-to { opacity: 0; }
.message-in-move { transition: none; }
.assistant-task-overlay.fade-enter-from .assistant-task,
.assistant-task-overlay.fade-leave-to .assistant-task { opacity: 0; transform: translateY(12px); }

:deep(.chat-citations) { display: block; margin-top: 14px; font-size: 14px; }
:deep(.chat-citations summary) { width: max-content; color: var(--color-brand-700); cursor: pointer; font-size: 13px; }
:deep(.chat-citations ul) { display: grid; gap: 8px; margin: 10px 0 0; padding: 0; list-style: none; }
:deep(.chat-citations li) { padding: 10px 12px; border: 1px solid var(--color-border); border-radius: 9px; background: var(--color-mint-050); }
:deep(.chat-citations strong),
:deep(.chat-citations small),
:deep(.chat-citations p) { display: block; }
:deep(.chat-citations strong) { font-size: 13px; }
:deep(.chat-citations small) { margin-top: 2px; color: var(--color-text-secondary); font-size: 12px; }
:deep(.chat-citations p) { margin: 5px 0 0; color: var(--color-text-secondary); font-size: 13px; line-height: 1.5; }

@keyframes chat-dot {
  0%, 80%, 100% { opacity: .28; transform: translateY(0); }
  40% { opacity: 1; transform: translateY(-3px); }
}

@media (max-width: 767px) {
  .chat-main { padding: 4px 16px 8px; }
  .chat-composer-wrap { padding-left: 12px; padding-right: 12px; }
  .chat-empty h1 { font-size: 26px; }
  .chat-message__user-content { max-width: 86%; }
  .chat-message__copy { opacity: 1; }
}

@media (prefers-reduced-motion: reduce) {
  .message-in-enter-active,
  .message-in-leave-active,
  .assistant-task,
  .chat-typing span { animation: none; transition: none; }
}
</style>
