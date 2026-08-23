<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { useAuth } from '../stores'
import { useAssistant } from '../composables/useAssistant'
import { AI_REGISTRATION_PROMPT } from '../features/assistant/registration'
import { filterSessionsByTitle } from '../features/assistant/session'
import AssistantShell from '../components/AssistantShell.vue'
import UiIcon from '../components/UiIcon.vue'
import CitationList from '../components/CitationList.vue'
import InterruptConfirm from '../components/InterruptConfirm.vue'

const router = useRouter()
const { user } = useAuth()
const assistant = useAssistant(user)
const input = ref('')
const query = ref('')
const end = ref(null)
const quickOpen = ref(false)
const composer = ref(null)
const taskPanel = ref(null)
const shell = ref(null)
const taskReturnFocus = ref(null)
let taskPreviousOverflow = ''
const suggestions = ['最近总是睡不好，挂什么科？', '查看我最近的预约', '我有待缴费用吗？', '如何查看就诊记录？']
const urgent = computed(() => /胸痛|呼吸困难|意识障碍|大量出血/.test([...assistant.activeSession.value?.messages || []].reverse().find((item) => item.role === 'user')?.content || ''))
const totalCharges = computed(() => assistant.context.value.charges.reduce((sum, item) => sum + Number(item.totalAmount || 0), 0))
const hasMessages = computed(() => Boolean(assistant.activeSession.value?.messages.length))
const visibleSessions = computed(() => filterSessionsByTitle(assistant.sessions.value, query.value))
const nextAppointment = computed(() => assistant.context.value.appointments[0])

watch(() => [assistant.activeSession.value?.messages.length, assistant.replying.value], async () => {
  await nextTick()
  const reduceMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
  end.value?.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'nearest' })
})

function send(text = input.value) {
  if (!text.trim() || assistant.replying.value || assistant.pendingInterrupt.value) return
  assistant.sendMessage(text)
  input.value = ''
  quickOpen.value = false
  nextTick(resetComposerHeight)
}

const renderMarkdown = (value) => DOMPurify.sanitize(marked.parse(value || ''))

function keydown(event) {
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
    event.preventDefault()
    send()
  }
}

function openTask(task) {
  if (task.type === 'registration') send(AI_REGISTRATION_PROMPT)
  else assistant.openTask(task)
  quickOpen.value = false
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
  composer.value.style.height = '40px'
  composer.value.style.overflowY = 'hidden'
}

function resizeComposer(event) {
  const textarea = event.target
  textarea.style.height = 'auto'
  const nextHeight = Math.min(textarea.scrollHeight, 140)
  textarea.style.height = `${Math.max(40, nextHeight)}px`
  textarea.style.overflowY = textarea.scrollHeight > 140 ? 'auto' : 'hidden'
}

onMounted(() => marked.setOptions({ breaks: true, gfm: true }))
onBeforeUnmount(() => {
  document.removeEventListener('keydown', onTaskKeydown)
  document.body.style.overflow = taskPreviousOverflow
})
</script>

<template>
  <AssistantShell ref="shell">
    <template #header-actions>
      <button class="btn btn--outline" type="button" @click="newChat"><UiIcon name="plus" :size="17" />新对话</button>
    </template>

    <template #sidebar>
      <button class="chat-history-new" type="button" @click="newChat"><UiIcon name="plus" :size="17" />新对话</button>
      <label class="chat-history-search">
        <UiIcon name="search" :size="16" />
        <input v-model="query" type="search" placeholder="搜索会话标题" aria-label="搜索会话标题">
      </label>
      <div class="chat-history-list">
        <p v-if="!visibleSessions.length" class="chat-history-empty">没有匹配的会话</p>
        <div v-for="session in visibleSessions" :key="session.id" class="chat-history-item" :class="{ 'is-active': session.id === assistant.activeId.value }">
          <button type="button" @click="selectSession(session.id)"><strong>{{ session.title }}</strong><small>{{ session.messages.length ? `${session.messages.length} 条消息` : '空会话' }}</small></button>
          <button v-if="assistant.sessions.value.length > 1" class="chat-history-item__delete" type="button" aria-label="删除会话" @click="assistant.deleteSession(session.id)">×</button>
        </div>
      </div>
      <p v-if="assistant.sessionError.value" class="chat-history-error">{{ assistant.sessionError.value }}</p>
    </template>

    <template #context>
      <section class="chat-context-card">
        <small>下一次就诊</small>
        <strong>{{ contextText('appointments', nextAppointment ? `${nextAppointment.deptName} · ${nextAppointment.staffName}` : '', '还没有预约') }}</strong>
        <button type="button" @click="viewContext({ type: 'registration', title: '预约挂号' })">查看 →</button>
      </section>
      <section class="chat-context-card">
        <small>待缴费用</small>
        <strong>{{ contextText('charges', assistant.context.value.charges.length ? `¥${totalCharges.toFixed(2)}` : '', '暂无待缴账单') }}</strong>
        <button type="button" @click="viewContext({ type: 'payment', title: '待缴费用' })">查看 →</button>
      </section>
      <section class="chat-context-card">
        <small>最近就诊</small>
        <strong>{{ contextText('visits', assistant.context.value.visits.length ? `${assistant.context.value.visits.length} 条记录` : '', '暂无就诊记录') }}</strong>
        <button type="button" @click="viewContext({ type: 'records', title: '就诊记录' })">查看 →</button>
      </section>
    </template>

    <template #chips="{ openContext }">
      <button class="assistant-chip" type="button" @click="openContext">下一次就诊</button>
      <button class="assistant-chip" type="button" @click="openContext">待缴</button>
      <button class="assistant-chip" type="button" @click="openContext">记录</button>
    </template>

    <div class="chat-page">
      <div v-if="urgent" class="chat-alerts">
        <div class="assistant-urgent" role="alert" aria-live="assertive"><strong>请优先处理急症</strong><span>前往急诊或拨打 120。</span></div>
      </div>

      <main class="chat-main" aria-label="健康助手对话">
        <div v-if="!hasMessages" class="chat-empty">
          <span class="chat-empty__mark" aria-hidden="true"><UiIcon name="ai" :size="24" /></span>
          <h2>有什么需要帮忙的？</h2>
          <p>描述症状，或告诉我想办理的事项。</p>
          <div class="chat-suggestions" aria-label="推荐问题">
            <button v-for="item in suggestions" :key="item" type="button" @click="send(item)">{{ item }}<span aria-hidden="true">↗</span></button>
          </div>
        </div>

        <div v-else class="chat-thread" aria-live="polite">
          <TransitionGroup name="message-in" tag="div" class="chat-message-list">
            <article v-for="message in assistant.activeSession.value.messages" :key="message.id" class="chat-message" :class="`chat-message--${message.role}`">
              <div v-if="message.role === 'user'" class="chat-message__user-content">{{ message.content }}</div>
              <template v-else>
                <div class="chat-message__assistant-label"><UiIcon name="ai" :size="14" />温润健康助手</div>
                <div class="chat-message__assistant-content"><div class="chat-md" v-html="renderMarkdown(message.content)" /><CitationList v-if="message.sources?.length" :sources="message.sources" /></div>
              </template>
            </article>
          </TransitionGroup>
          <InterruptConfirm v-if="assistant.pendingInterrupt.value" :interrupt="assistant.pendingInterrupt.value" :loading="assistant.replying.value" @confirm="assistant.resumeInterrupt(true)" @reject="assistant.resumeInterrupt(false)" />
          <div v-if="assistant.replying.value && !assistant.streaming.value" class="chat-status" aria-live="polite"><span class="chat-status__dot" />{{ assistant.streamStatus.value || '正在整理信息…' }}</div>
          <div ref="end" />
        </div>
      </main>

      <footer class="chat-composer-wrap">
        <Transition name="pop">
          <div v-if="quickOpen" class="chat-quick-menu" role="menu">
            <button type="button" role="menuitem" @click="openTask({ type: 'registration', title: '预约挂号' })"><UiIcon name="calendar" :size="17" />预约挂号</button>
            <button type="button" role="menuitem" @click="openTask({ type: 'payment', title: '待缴费用' })"><UiIcon name="wallet" :size="17" />查看待缴</button>
            <button type="button" role="menuitem" @click="openTask({ type: 'records', title: '就诊记录' })"><UiIcon name="record" :size="17" />就诊记录</button>
          </div>
        </Transition>
        <div class="chat-composer">
          <button class="chat-composer__plus" type="button" aria-label="打开快捷入口" :aria-expanded="quickOpen" @click="quickOpen = !quickOpen"><UiIcon name="plus" :size="19" /></button>
          <textarea ref="composer" v-model="input" rows="1" :disabled="assistant.replying.value || !!assistant.pendingInterrupt.value" :placeholder="assistant.pendingInterrupt.value ? '请先完成上方确认…' : '输入消息…'" @input="resizeComposer" @keydown="keydown" />
          <button v-if="assistant.replying.value" class="chat-composer__stop" type="button" @click="assistant.stopReply">停止</button>
          <button v-else class="chat-composer__send" type="button" :disabled="!input.trim() || !!assistant.pendingInterrupt.value" aria-label="发送消息" @click="send"><UiIcon name="send" :size="18" /></button>
        </div>
        <p class="chat-disclaimer">AI 提供健康信息和就医协助，不替代医生诊断。</p>
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
.chat-page{min-height:0;height:100%;display:flex;flex-direction:column}.chat-alerts{width:min(840px,100%);margin:0 auto;padding:12px 20px 0}.assistant-urgent{display:flex;align-items:flex-start;gap:9px;margin-top:8px;padding:10px 14px;border:1px solid #f1b8b3;border-radius:10px;background:var(--color-danger-bg);color:var(--color-danger);font-size:14px;line-height:1.5}.chat-main{width:min(840px,100%);flex:1;min-height:0;overflow:auto;margin:0 auto;padding:0 20px}.chat-empty{display:flex;flex-direction:column;align-items:center;padding:clamp(48px,10vh,112px) 20px 40px;text-align:center}.chat-empty__mark{display:grid;place-items:center;width:48px;height:48px;margin-bottom:18px;border-radius:10px;background:var(--color-brand-700);color:#fff}.chat-empty h2{margin:0 0 8px;font-size:28px}.chat-empty p{margin:0;color:var(--color-text-secondary)}.chat-suggestions{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;width:min(620px,100%);margin-top:28px}.chat-suggestions button{display:flex;align-items:center;justify-content:space-between;gap:12px;min-height:48px;padding:11px 13px;border:1px solid var(--color-border);border-radius:10px;background:var(--color-surface);color:var(--color-text);cursor:pointer;text-align:left;font:inherit;font-size:14px}.chat-suggestions button:hover{border-color:var(--color-brand-600);background:var(--color-mint-050)}.chat-suggestions button span{color:var(--color-brand-700)}.chat-thread{padding:12px 0 28px}.chat-message{margin:0 0 26px}.chat-message--user{display:flex;justify-content:flex-end}.chat-message__user-content{max-width:min(680px,82%);padding:11px 15px;border-radius:10px 10px 4px 10px;background:var(--color-brand-700);color:#fff;line-height:1.65}.chat-message--assistant{max-width:760px}.chat-message__assistant-label{display:flex;align-items:center;gap:5px;margin-bottom:7px;color:var(--color-text-secondary);font-size:12px}.chat-message__assistant-content{color:var(--color-text);line-height:1.75;font-size:16px}.chat-message__assistant-content :deep(p){margin:0 0 10px}.chat-message__assistant-content :deep(p:last-child){margin-bottom:0}.chat-message__assistant-content :deep(ul),.chat-message__assistant-content :deep(ol){padding-left:22px}.chat-status{display:flex;align-items:center;gap:8px;color:var(--color-text-secondary);font-size:14px}.chat-status__dot{width:7px;height:7px;border-radius:50%;background:var(--color-brand-600)}.chat-composer-wrap{position:relative;width:min(840px,100%);margin:0 auto;padding:10px 20px max(8px,env(safe-area-inset-bottom));background:linear-gradient(180deg,transparent 0%,var(--color-bg) 22%)}.chat-composer{position:relative;display:flex;align-items:flex-end;gap:8px;min-height:58px;padding:8px 10px;border:1px solid var(--color-border-strong);border-radius:10px;background:var(--color-surface);box-shadow:var(--shadow-sm);transition:border-color .16s,box-shadow .16s}.chat-composer:focus-within{border-color:var(--color-brand-600);box-shadow:0 0 0 3px rgba(18,150,136,.22),var(--shadow)}.chat-composer__plus,.chat-composer__send{display:grid;place-items:center;width:40px;height:40px;flex:0 0 40px;border:0;border-radius:50%;cursor:pointer}.chat-composer__plus{background:transparent;color:var(--color-text-secondary)}.chat-composer__plus:hover{background:var(--color-mint-100);color:var(--color-brand-700)}.chat-composer__send{background:var(--color-brand-700);color:#fff;transition:background-color var(--motion-fast) var(--ease-standard)}.chat-composer__send:not(:disabled):hover{background:var(--color-brand-800)}.chat-composer__send:disabled{opacity:.45;cursor:not-allowed}.chat-composer__stop{min-height:40px;padding:0 12px;border:1px solid var(--color-border-strong);border-radius:18px;background:var(--color-mint-050);color:var(--color-brand-700);cursor:pointer}.chat-composer textarea,.chat-composer textarea:focus,.chat-composer textarea:focus-visible{min-height:40px;max-height:140px;flex:1;width:100%;padding:8px 2px;resize:none;border:0;outline:0 !important;box-shadow:none !important;background:transparent;color:var(--color-text);font:inherit;line-height:1.5}.chat-disclaimer{margin:7px 0 0;color:var(--color-text-secondary);font-size:12px;text-align:center}.chat-quick-menu{position:absolute;bottom:72px;left:20px;z-index:4;display:grid;gap:4px;min-width:160px;padding:6px;border:1px solid var(--color-border);border-radius:12px;background:var(--color-surface);box-shadow:0 12px 28px rgba(18,52,45,.12)}.chat-quick-menu button{display:flex;align-items:center;gap:8px;min-height:38px;padding:0 9px;border:0;border-radius:7px;background:transparent;color:var(--color-text);cursor:pointer;text-align:left}.chat-quick-menu button:hover{background:var(--color-mint-100);color:var(--color-brand-700)}.chat-history-new{display:flex;align-items:center;gap:8px;width:100%;min-height:44px;margin:0 0 14px;padding:0 12px;border:1px solid var(--color-border-strong);border-radius:9px;background:var(--color-mint-050);color:var(--color-brand-700);cursor:pointer;font:inherit}.chat-history-search{display:flex;align-items:center;gap:8px;min-height:44px;margin:0 0 14px;padding:0 12px;border:1px solid var(--color-border);border-radius:9px;background:var(--color-surface);color:var(--color-text-secondary)}.chat-history-search input{width:100%;border:0;outline:0;background:transparent;color:var(--color-text);font:inherit}.chat-history-list{display:grid;gap:4px}.chat-history-empty,.chat-history-error{margin:8px 0 0;font-size:14px}.chat-history-empty{color:var(--color-text-secondary)}.chat-history-error{color:var(--color-danger)}.chat-history-item{display:flex;align-items:center;border-radius:9px}.chat-history-item.is-active{background:var(--color-mint-100)}.chat-history-item>button:first-child{min-width:0;flex:1;padding:10px;border:0;background:transparent;color:var(--color-text);cursor:pointer;text-align:left}.chat-history-item strong,.chat-history-item small{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.chat-history-item small{margin-top:3px;color:var(--color-text-secondary);font-size:12px}.chat-history-item__delete{width:36px;height:36px;margin-right:4px;border:0;background:transparent;color:var(--color-text-secondary);cursor:pointer;font-size:18px}.chat-history-item__delete:hover{color:var(--color-danger)}.chat-context-card{padding:16px 0;border-bottom:1px solid var(--color-border)}.chat-context-card small,.chat-context-card strong{display:block}.chat-context-card small{color:var(--color-text-secondary);font-size:13px}.chat-context-card strong{margin:7px 0 12px}.chat-context-card button{padding:0;border:0;background:none;color:var(--color-brand-700);cursor:pointer;font:inherit;font-size:14px;font-weight:600}.assistant-chip{flex:0 0 auto;min-height:36px;padding:0 12px;border:1px solid var(--color-border);border-radius:999px;background:var(--color-surface);color:var(--color-brand-700);cursor:pointer;font:inherit;font-size:13px}.icon-button{display:grid;place-items:center;width:40px;height:40px;border:1px solid var(--color-border);border-radius:9px;background:var(--color-surface);color:var(--color-text-secondary);cursor:pointer;font-size:20px}.icon-button:hover{border-color:var(--color-brand-600);color:var(--color-brand-700)}.assistant-task-overlay{position:fixed;inset:0;z-index:50;display:grid;place-items:center;padding:20px;background:rgba(18,52,45,.38)}.assistant-task{position:relative;width:min(560px,100%);max-height:85vh;overflow:auto;padding:28px;border-radius:20px;background:#fff;box-shadow:0 20px 48px rgba(18,52,45,.2);opacity:1;transform:translateY(0);transition:opacity var(--motion-med) var(--ease-enter),transform var(--motion-med) var(--ease-enter)}.assistant-task__close{position:absolute;top:18px;right:18px}.assistant-task h2{margin:6px 0}.assistant-task>p{color:var(--color-text-secondary)}.assistant-task__options{display:grid;gap:8px;margin:18px 0}.assistant-task__options button{display:flex;justify-content:space-between;align-items:center;padding:14px;border:1px solid var(--color-border);border-radius:10px;background:#fff;color:var(--color-text);cursor:pointer;text-align:left}.assistant-task__options strong,.assistant-task__options small{display:block}.assistant-task__options small{margin-top:3px;color:var(--color-text-secondary)}.assistant-task__options b{color:var(--color-text)}.assistant-task__empty{padding:18px;border-radius:10px;background:var(--color-mint-050);color:var(--color-text-secondary);text-align:center}.btn--full{width:100%}.chat-message-list{display:block}.message-in-enter-active{transition:opacity var(--motion-med) var(--ease-enter),transform var(--motion-med) var(--ease-enter)}.message-in-enter-from{opacity:0;transform:translateY(4px)}.message-in-leave-active{transition:opacity var(--motion-exit) var(--ease-exit)}.message-in-leave-to{opacity:0}.message-in-move{transition:none}.assistant-task-overlay.fade-enter-from .assistant-task,.assistant-task-overlay.fade-leave-to .assistant-task{opacity:0;transform:translateY(12px)}.assistant-task-overlay.fade-leave-active .assistant-task{transition-duration:var(--motion-exit);transition-timing-function:var(--ease-exit)}
@media(max-width:767px){.chat-empty{padding:32px 0 24px}.chat-empty h2{font-size:24px}.chat-suggestions{grid-template-columns:1fr;margin-top:22px}.chat-message__user-content{max-width:90%}.chat-alerts,.chat-main,.chat-composer-wrap{width:100%}.chat-alerts{padding:10px 16px 0}.chat-main{padding:0 16px}.chat-composer-wrap{padding-left:16px;padding-right:16px}.chat-quick-menu{left:16px}}
@media(prefers-reduced-motion:reduce){.message-in-enter-active,.message-in-leave-active,.assistant-task{transition:none}}
</style>
<style scoped>
:deep(.chat-citations){display:block;margin-top:14px;font-size:14px}
:deep(.chat-citations summary){width:max-content;color:var(--color-brand-700);cursor:pointer;font-size:13px}
:deep(.chat-citations ul){display:grid;gap:8px;margin:10px 0 0;padding:0;list-style:none}
:deep(.chat-citations li){padding:10px 12px;border:1px solid var(--color-border);border-radius:9px;background:var(--color-mint-050)}
:deep(.chat-citations strong),:deep(.chat-citations small),:deep(.chat-citations p){display:block}
:deep(.chat-citations strong){font-size:13px}:deep(.chat-citations small){margin-top:2px;color:var(--color-text-secondary);font-size:12px}:deep(.chat-citations p){margin:5px 0 0;color:var(--color-text-secondary);font-size:13px;line-height:1.5}
:deep(.assistant-interrupt){margin-top:14px;padding:16px;border:1px solid #f0d68d;border-radius:12px;background:var(--color-warning-bg)}
:deep(.assistant-interrupt small){color:var(--color-warning);font-weight:700}
:deep(.assistant-interrupt h3){margin:6px 0 12px;font-size:16px}
:deep(.assistant-interrupt dl){display:grid;gap:6px;margin:0 0 14px}:deep(.assistant-interrupt dl>div){display:flex;justify-content:space-between;gap:12px}:deep(.assistant-interrupt dt){color:var(--color-text-secondary);font-size:14px}:deep(.assistant-interrupt dd){margin:0;font-weight:600;text-align:right}
:deep(.assistant-interrupt__actions){display:flex;gap:8px}:deep(.assistant-interrupt__actions button){min-height:44px;flex:1;border:1px solid var(--color-border-strong);border-radius:9px;background:#fff;color:var(--color-text);cursor:pointer}:deep(.assistant-interrupt__actions .is-primary){border-color:var(--color-brand-700);background:var(--color-brand-700);color:#fff;font-weight:600}
</style>
