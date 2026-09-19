<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuth } from '../stores'
import { listSchedules } from '../api'
import { formatDate, formatTime, formatTimePeriod, formatVisitSchedule } from '../utils'
import { todayISO } from '../utils/scheduleDate'
import { bookableToday, nextAppointment } from '../features/home/overview'
import UiIcon from './UiIcon.vue'

const props = defineProps({
  appointments: { type: Array, default: () => [] },
  appointmentsError: { type: Boolean, default: false },
})
const emit = defineEmits(['prompt'])

const router = useRouter()
const route = useRoute()
const { user } = useAuth()
const visualPreview = import.meta.env.DEV && route.query.preview === '1'
const schedules = ref([])
const scheduleError = ref(false)

const name = computed(() => user.value?.realName || user.value?.username || '患者')
const next = computed(() => nextAppointment(props.appointments))
const appointmentSummary = computed(() => (next.value
  ? `${formatVisitSchedule(next.value.workDate, next.value.timePeriod)} · ${next.value.deptName} · ${next.value.staffName}`
  : (props.appointmentsError ? '就诊信息暂时无法获取' : '暂无待就诊预约')))

const agentActions = [
  { icon: 'calendar', label: '帮我挂号', prompt: '我想预约挂号，请帮我看看近期可用号源。' },
  { icon: 'record', label: '查预约', prompt: '帮我查看最近的预约和就诊安排。' },
  { icon: 'hospital', label: '找科室', prompt: '我不确定该挂什么科，请根据症状帮我判断。' },
]

const previewSchedules = [
  { id: 1, deptName: '心内科', staffName: '张医生', timePeriod: '上午', remainingCount: 8, registerFee: 30 },
  { id: 2, deptName: '呼吸内科', staffName: '李医生', timePeriod: '下午', remainingCount: 5, registerFee: 25 },
  { id: 3, deptName: '消化内科', staffName: '王医生', timePeriod: '上午', remainingCount: 12, registerFee: 25 },
]

function openVisit() {
  router.push(next.value ? `/registration/${next.value.id}` : '/registration')
}

onMounted(async () => {
  if (visualPreview) {
    schedules.value = previewSchedules
    return
  }
  try {
    schedules.value = bookableToday(await listSchedules({ workDate: todayISO() }))
  } catch {
    scheduleError.value = true
  }
})
</script>

<template>
  <section class="welcome" aria-label="首页概览">
    <div class="welcome__head">
      <p>{{ formatDate(new Date()) }} · {{ formatTime() }}</p>
      <h1>{{ name }}，今天想先了解什么？</h1>
    </div>

    <button
      class="visit-strip"
      type="button"
      :aria-label="next ? `查看下次就诊：${appointmentSummary}` : '开始预约挂号'"
      @click="openVisit"
    >
      <span class="visit-strip__icon"><UiIcon name="calendar" :size="20" /></span>
      <span class="visit-strip__body">
        <small>{{ next ? '下次就诊' : '就诊安排' }}</small>
        <strong>{{ appointmentSummary }}</strong>
      </span>
      <span class="visit-strip__action">{{ next ? '查看' : '去挂号' }}<UiIcon name="arrowRight" :size="16" /></span>
    </button>

    <div class="welcome__actions" aria-label="常用任务">
      <button v-for="action in agentActions" :key="action.label" type="button" @click="emit('prompt', action.prompt)">
        <UiIcon :name="action.icon" :size="16" />{{ action.label }}
      </button>
    </div>

    <section class="welcome__panel" aria-labelledby="welcome-schedule-title">
      <div class="welcome__panel-head">
        <div><span>实时信息</span><h2 id="welcome-schedule-title">今日可预约</h2></div>
        <RouterLink to="/registration">全部号源<UiIcon name="arrowRight" :size="16" /></RouterLink>
      </div>
      <p v-if="scheduleError" class="welcome__state">号源暂时无法获取，可让助手稍后再查。</p>
      <div v-else-if="schedules.length" class="schedule-stack">
        <button
          v-for="schedule in schedules"
          :key="schedule.id"
          type="button"
          @click="emit('prompt', `帮我看看${schedule.deptName}${schedule.staffName}的可预约时间。`)"
        >
          <span class="schedule-stack__icon"><UiIcon name="hospital" :size="18" /></span>
          <span><strong>{{ schedule.deptName }} · {{ schedule.staffName }}</strong><small>{{ formatTimePeriod(schedule.timePeriod) }} · 挂号费 ¥{{ schedule.registerFee }}</small></span>
          <b>余 {{ schedule.remainingCount }}</b>
        </button>
      </div>
      <p v-else class="welcome__state">今日暂无可预约号源，可让助手查询后续排班。</p>
    </section>
  </section>
</template>

<style scoped>
.welcome {
  --home-ink: #17343b;
  --home-muted: #60777d;
  --home-teal: #0f8f82;
  --home-aqua: #dff5f2;
  width: 100%;
  padding: 20px 0 8px;
  color: var(--home-ink);
}
.welcome__head p { margin: 0 0 5px; color: #5c7a7b; font-size: 12px; font-weight: 650; letter-spacing: .04em; }
.welcome__head h1 { margin: 0; color: #153b3c; font-size: clamp(26px, 3vw, 34px); font-weight: 750; line-height: 1.2; letter-spacing: -.03em; }

.visit-strip { width: 100%; min-height: 72px; display: grid; grid-template-columns: auto minmax(0,1fr) auto; align-items: center; gap: 13px; margin-top: 22px; padding: 11px 13px; border: 1px solid rgba(15, 143, 130, .2); border-radius: 18px; background: #f6fbfb; color: inherit; cursor: pointer; text-align: left; font: inherit; transition: border-color 160ms ease, box-shadow 160ms ease; }
.visit-strip:hover, .visit-strip:focus-visible { border-color: var(--home-teal); box-shadow: 0 10px 28px rgba(27, 78, 81, .1); }
.visit-strip__icon { width: 44px; height: 44px; display: grid; place-items: center; border-radius: 13px; background: var(--home-aqua); color: var(--home-teal); }
.visit-strip__body { min-width: 0; }
.visit-strip__body small, .visit-strip__body strong { display: block; }
.visit-strip__body small { margin-bottom: 4px; color: var(--home-muted); font-size: 11px; }
.visit-strip__body strong { overflow: hidden; font-size: 14px; text-overflow: ellipsis; white-space: nowrap; }
.visit-strip__action { display: inline-flex; align-items: center; gap: 2px; color: var(--home-teal); font-size: 12px; font-weight: 750; white-space: nowrap; }

.welcome__actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 18px; }
.welcome__actions button { display: inline-flex; align-items: center; gap: 8px; min-height: 40px; padding: 0 14px; border: 1px solid #d9e9e8; border-radius: 999px; background: #f7fbfb; color: var(--home-ink); cursor: pointer; font: inherit; font-size: 13px; font-weight: 650; transition: border-color 160ms ease, background-color 160ms ease; }
.welcome__actions button svg { color: var(--home-teal); }
.welcome__actions button:hover, .welcome__actions button:focus-visible { border-color: #73bdb5; background: #eef8f7; }

.welcome__panel { margin-top: 26px; }
.welcome__panel-head { display: flex; align-items: end; justify-content: space-between; gap: 12px; margin-bottom: 8px; }
.welcome__panel-head span { display: block; margin-bottom: 3px; color: var(--home-teal); font-size: 10px; font-weight: 800; letter-spacing: .11em; }
.welcome__panel-head h2 { margin: 0; color: var(--home-ink); font-size: 17px; }
.welcome__panel-head a { min-height: 36px; display: inline-flex; align-items: center; gap: 2px; color: var(--home-muted); font-size: 11px; font-weight: 700; white-space: nowrap; }

.schedule-stack { display: grid; }
.schedule-stack button { min-width: 0; min-height: 62px; display: grid; grid-template-columns: auto minmax(0,1fr) auto; align-items: center; gap: 10px; padding: 10px 0; border: 0; border-bottom: 1px solid #e1ebeb; background: transparent; color: inherit; cursor: pointer; font: inherit; text-align: left; }
.schedule-stack button:first-child { border-top: 1px solid #e1ebeb; }
.schedule-stack button:hover span:nth-child(2) strong, .schedule-stack button:focus-visible span:nth-child(2) strong { color: var(--home-teal); }
.schedule-stack__icon { width: 34px; height: 34px; display: grid; place-items: center; border-radius: 11px; background: #e9f6f4; color: var(--home-teal); }
.schedule-stack strong, .schedule-stack small { display: block; }
.schedule-stack strong { overflow: hidden; font-size: 13px; text-overflow: ellipsis; white-space: nowrap; }
.schedule-stack small { margin-top: 3px; color: var(--home-muted); font-size: 11px; }
.schedule-stack b { color: var(--home-teal); font-size: 11px; white-space: nowrap; }
.welcome__state { min-height: 62px; display: flex; align-items: center; margin: 0; color: var(--home-muted); font-size: 12px; line-height: 1.6; }

@media (max-width: 767px) {
  .welcome { padding-top: 12px; }
  .welcome__head h1 { font-size: 25px; }
  .visit-strip { min-height: 66px; margin-top: 18px; padding: 9px 10px; border-radius: 16px; }
  .visit-strip__icon { width: 40px; height: 40px; border-radius: 12px; }
  .visit-strip__body strong { font-size: 12px; }
  .visit-strip__action { font-size: 11px; }
}
@media (prefers-reduced-motion: reduce) {
  .visit-strip, .welcome__actions button { transition: none; }
}
</style>
