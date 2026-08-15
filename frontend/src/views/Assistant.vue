<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { useAuth } from '../stores'
import { useAssistant } from '../composables/useAssistant'
import { listSchedules } from '../api'
import { MODE_CLASSIC, writeMode } from '../features/experience/mode'
import UiIcon from '../components/UiIcon.vue'

const router = useRouter()
const { user } = useAuth()
const assistant = useAssistant(user)
const input = ref(''), end = ref(null)
const schedules = ref([]), selected = ref(null), taskLoading = ref(false), taskSaving = ref(false), taskError = ref('')
const suggestions = ['最近总是睡不好，帮我判断该挂什么科', '查看我最近的预约', '我有待缴费用吗？', '如何查看就诊记录？']
const urgent = computed(() => /胸痛|呼吸困难|意识障碍|大量出血/.test([...assistant.activeSession.value?.messages || []].reverse().find((item) => item.role === 'user')?.content || ''))
const totalCharges = computed(() => assistant.context.value.charges.reduce((sum, item) => sum + Number(item.totalAmount || 0), 0))
watch(() => [assistant.activeSession.value?.messages.length, assistant.replying.value], async () => { await nextTick(); end.value?.scrollIntoView({ behavior: 'smooth' }) })
function send(text = input.value) { if (!text.trim() || assistant.replying.value) return; assistant.sendMessage(text); input.value = '' }
const renderMarkdown = (value) => DOMPurify.sanitize(marked.parse(value || ''))
function keydown(event) { if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) { event.preventDefault(); send() } }
function switchClassic() { writeMode(MODE_CLASSIC); router.push('/home') }
async function openTask(task) {
  assistant.openTask(task)
  if (task.type !== 'registration') return
  taskLoading.value = true; taskError.value = ''; selected.value = null
  try { schedules.value = (await listSchedules({ workDate: new Date().toISOString().slice(0, 10) }) || []).filter((item) => item.remainingCount > 0) }
  catch { taskError.value = '暂时无法获取可预约的排班。' }
  finally { taskLoading.value = false }
}
async function register() {
  if (!selected.value) return
  taskSaving.value = true
  try { await assistant.submitRegistration(selected.value.id); assistant.closeTask() }
  catch (error) { taskError.value = error.message || '挂号失败，请稍后重试。' }
  finally { taskSaving.value = false }
}
onMounted(() => marked.setOptions({ breaks: true, gfm: true }))
</script>

<template>
  <div class="agent-shell">
    <div class="agent-shell__grain" />
    <aside class="agent-history">
      <div class="agent-history__brand"><span><UiIcon name="logo" :size="23" /></span><div><strong>温润诊所</strong><small>WARM CLINIC · AI CARE</small></div></div>
      <button class="agent-history__new" @click="assistant.newChat">＋ 开始新的问诊</button><p class="agent-history__title">最近对话</p>
      <div class="agent-history__list"><div v-for="session in assistant.sessions.value" :key="session.id" class="agent-history__item" :class="{ 'is-active': session.id===assistant.activeId.value }"><button @click="assistant.activeId.value=session.id"><strong>{{ session.title }}</strong><small>{{ session.messages.length ? `${session.messages.length} 条消息` : '尚未开始' }}</small></button><button v-if="assistant.sessions.value.length>1" @click="assistant.deleteSession(session.id)">×</button></div></div>
      <div class="agent-history__user"><b>{{ (user?.realName || user?.username || '患')[0] }}</b><span><strong>{{ user?.realName || user?.username || '患者' }}</strong><small>患者端 · 数据已加密</small></span></div>
    </aside>
    <main class="agent-main">
      <header class="agent-header"><div class="agent-header__brand"><span><UiIcon name="logo" :size="18" /></span><div><strong>温润 · 随身诊室</strong><small><i />智能体在线</small></div></div><div class="agent-header__actions"><button @click="assistant.newChat">新对话</button><button @click="switchClassic">传统版</button></div></header>
      <div v-if="!assistant.activeSession.value?.messages.length" class="agent-welcome">
        <div class="agent-welcome__orb"><UiIcon name="logo" :size="40" /></div><p>你好，{{ user?.realName || user?.username || '朋友' }}</p><h1>把身体的困扰，<em>慢慢告诉我。</em></h1><span>我可以帮你分诊、预约、查看就诊信息和解释账单。重要决定仍由你确认，并交给医生判断。</span>
        <div class="agent-welcome__suggestions"><button v-for="item in suggestions" :key="item" @click="send(item)">{{ item }}<b>→</b></button></div>
        <div class="agent-welcome__actions"><button @click="openTask({type:'registration',title:'预约挂号'})"><UiIcon name="calendar" :size="19" /><span><strong>预约挂号</strong><small>选择科室和时间</small></span><b>→</b></button><button @click="openTask({type:'payment',title:'待缴费用'})"><UiIcon name="wallet" :size="19" /><span><strong>查看费用</strong><small>核对待缴账单</small></span><b>→</b></button><button @click="openTask({type:'records',title:'就诊记录'})"><UiIcon name="record" :size="19" /><span><strong>就诊记录</strong><small>回顾诊疗信息</small></span><b>→</b></button></div>
      </div>
      <div v-else class="agent-thread">
        <div v-if="urgent" class="agent-alert"><strong>出现急症风险提示</strong><span>如有胸痛、呼吸困难、意识障碍或大量出血，请立即拨打 120 或前往急诊。</span></div>
        <article v-for="(message,index) in assistant.activeSession.value.messages" :key="index" class="agent-message" :class="`agent-message--${message.role==='user'?'user':'assistant'}`"><span v-if="message.role!=='user'" class="agent-message__avatar"><UiIcon name="ai" :size="16" /></span><div><p v-if="message.role==='user'">{{ message.content }}</p><div v-else v-html="renderMarkdown(message.content)" /></div></article>
        <div v-if="assistant.replying.value && !assistant.streaming.value" class="agent-typing"><span /><span /><span />正在整理信息…</div><div ref="end" />
      </div>
      <footer class="agent-composer"><div><textarea v-model="input" rows="1" :disabled="assistant.replying.value" placeholder="描述症状，或告诉我想办理什么…" @keydown="keydown" /><button v-if="assistant.replying.value" class="agent-composer__stop" @click="assistant.stopReply">停止</button><button v-else :disabled="!input.trim()" @click="send()">↑</button></div><p>AI 提供健康信息和就医协助，不替代医生诊断；如遇急症请立即拨打 120。</p></footer>
    </main>
    <aside class="agent-context">
      <div class="agent-context__intro"><p>就诊上下文</p><h2>把需要处理的事，<br>放在我身边。</h2><span><i />数据实时同步</span></div>
      <section class="agent-context__card"><small>下一次就诊</small><strong>{{ assistant.context.value.appointments[0] ? `${assistant.context.value.appointments[0].deptName} · ${assistant.context.value.appointments[0].staffName}` : '还没有预约' }}</strong><p>需要时告诉我，我来协助安排。</p><button @click="openTask({type:'registration',title:'预约挂号'})">查看详情 →</button></section>
      <section class="agent-context__card"><small>待缴费用</small><strong>{{ assistant.context.value.charges.length ? `¥${totalCharges.toFixed(2)}` : '暂无待缴账单' }}</strong><p>{{ assistant.context.value.charges.length }} 笔账单等待处理</p><button @click="openTask({type:'payment',title:'待缴费用'})">查看详情 →</button></section>
      <section class="agent-context__card"><small>最近就诊</small><strong>{{ assistant.context.value.visits.length ? `${assistant.context.value.visits.length} 条记录` : '暂无就诊记录' }}</strong><p>查看过往就诊和检查信息。</p><button @click="openTask({type:'records',title:'就诊记录'})">查看详情 →</button></section>
    </aside>
    <div v-if="assistant.task.value" class="agent-task-overlay" @mousedown.self="assistant.closeTask"><section class="agent-task"><div class="agent-task__handle" /><button class="agent-task__close" @click="assistant.closeTask">×</button><small>健康服务</small><h2>{{ assistant.task.value.title }}</h2>
      <template v-if="assistant.task.value.type==='registration'"><p>选择可预约的排班，最终提交前由你确认。</p><div v-if="taskLoading" class="agent-task__loading">正在查询可预约排班…</div><div v-else class="agent-task__options"><button v-for="schedule in schedules" :key="schedule.id" :class="{'is-selected':selected?.id===schedule.id}" @click="selected=schedule"><strong>{{ schedule.deptName }} · {{ schedule.staffName }}</strong><span>{{ schedule.workDate }} · {{ schedule.timePeriod }} · 余号 {{ schedule.remainingCount }}</span><b>¥{{ schedule.registerFee }}</b></button><div v-if="!schedules.length" class="agent-task__empty">今天暂无可预约排班。</div></div><div v-if="taskError" class="agent-task__error">{{ taskError }}</div><button class="agent-task__submit" :disabled="!selected || taskSaving" @click="register">{{ taskSaving ? '正在提交…' : '确认挂号' }}</button></template>
      <template v-else-if="assistant.task.value.type==='payment'"><p>确认账单后将在安全支付页继续办理。</p><div class="agent-task__options"><button v-for="charge in assistant.context.value.charges" :key="charge.id" @click="router.push(`/payment/${charge.id}`);assistant.closeTask()"><strong>{{ charge.orderNo || '门诊费用' }}</strong><span>{{ charge.createTime || '待缴费' }}</span><b>¥{{ Number(charge.totalAmount||0).toFixed(2) }}</b></button><div v-if="!assistant.context.value.charges.length" class="agent-task__empty">目前没有待缴账单。</div></div></template>
      <template v-else><p>就诊记录保留在传统服务中，便于完整查看。</p><div class="agent-task__empty">你可以查看历史挂号、就诊信息和个人档案。</div><button class="agent-task__submit" @click="router.push('/registration');assistant.closeTask()">查看就诊记录</button></template>
    </section></div>
  </div>
</template>
