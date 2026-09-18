<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth } from '../stores'
import { listRegistrations, listSchedules } from '../api'
import { formatDate, formatTime, formatTimePeriod, formatVisitSchedule } from '../utils'
import { isBookableSchedule, todayISO } from '../utils/scheduleDate'
import AppShell from '../components/AppShell.vue'
import UiIcon from '../components/UiIcon.vue'

const router = useRouter()
const { user } = useAuth()
const visualPreview = import.meta.env.DEV && new URLSearchParams(window.location.search).has('preview')
const data = ref({ registrations: [], schedules: [] })
const sectionErrors = ref({ registrations: false, schedules: false })
const loading = ref(true)

const name = computed(() => user.value?.realName || user.value?.username || '患者')
const nextRegistration = computed(() => data.value.registrations.find((item) => item.status === 1))
const availableSchedules = computed(() => data.value.schedules.slice(0, 3))
const appointmentSummary = computed(() => nextRegistration.value
  ? `${formatVisitSchedule(nextRegistration.value.workDate, nextRegistration.value.timePeriod)} · ${nextRegistration.value.deptName} · ${nextRegistration.value.staffName}`
  : (sectionErrors.value.registrations ? '就诊信息暂时无法获取' : '暂无待就诊预约'))

const agentActions = [
  { icon: 'calendar', label: '帮我挂号', prompt: '我想预约挂号，请帮我看看近期可用号源。' },
  { icon: 'record', label: '查预约', prompt: '帮我查看最近的预约和就诊安排。' },
  { icon: 'hospital', label: '找科室', prompt: '我不确定该挂什么科，请根据症状帮我判断。' },
]

const previewData = {
  registrations: [{ id: 1, status: 1, deptName: '心内科', staffName: '张医生', workDate: '2026-09-18', timePeriod: '上午' }],
  schedules: [
    { id: 1, deptName: '心内科', staffName: '张医生', timePeriod: '上午', remainingCount: 8, registerFee: 30 },
    { id: 2, deptName: '呼吸内科', staffName: '李医生', timePeriod: '下午', remainingCount: 5, registerFee: 25 },
    { id: 3, deptName: '消化内科', staffName: '王医生', timePeriod: '上午', remainingCount: 12, registerFee: 25 },
  ],
}

function openAssistant(text = '') {
  const prompt = text.trim()
  router.push({ path: '/assistant', query: { ...(prompt ? { prompt } : {}), ...(visualPreview ? { preview: '1' } : {}) } })
}

onMounted(async () => {
  if (visualPreview) {
    data.value = previewData
    loading.value = false
    return
  }
  if (!user.value?.userId) return void (loading.value = false)
  const results = await Promise.allSettled([
    listRegistrations({ userId: user.value.userId }),
    listSchedules({ workDate: todayISO() }),
  ])
  const value = (result) => result.status === 'fulfilled' && Array.isArray(result.value) ? result.value : []
  sectionErrors.value = {
    registrations: results[0].status === 'rejected',
    schedules: results[1].status === 'rejected',
  }
  data.value = {
    registrations: value(results[0]),
    schedules: value(results[1]).filter((item) => Number(item.remainingCount) > 0 && isBookableSchedule(item.workDate, item.timePeriod)),
  }
  loading.value = false
})
</script>

<template>
  <AppShell :padded="false">
    <div class="agent-home" :aria-busy="loading">
      <header class="agent-home__header">
        <div class="agent-home__header-inner">
          <div class="agent-home__brand-row">
            <RouterLink class="agent-brand" to="/home" aria-label="温润医院首页">
              <span class="agent-brand__mark"><UiIcon name="logo" :size="22" /></span>
              <span><strong>温润医院</strong><small>WENRUN CARE</small></span>
            </RouterLink>
            <span class="agent-home__emergency"><UiIcon name="alert" :size="15" />急症请拨打 120</span>
          </div>

          <div class="agent-home__welcome">
            <p>{{ formatDate(new Date()) }} · {{ formatTime() }}</p>
            <h1>{{ name }}，今天想先了解什么？</h1>
          </div>

          <button
            class="visit-strip"
            type="button"
            :aria-label="nextRegistration ? `查看下次就诊：${appointmentSummary}` : '开始预约挂号'"
            @click="router.push(nextRegistration ? `/registration/${nextRegistration.id}` : '/registration')"
          >
            <span class="visit-strip__icon"><UiIcon name="calendar" :size="20" /></span>
            <span class="visit-strip__body">
              <small>{{ nextRegistration ? '下次就诊' : '就诊安排' }}</small>
              <strong>{{ appointmentSummary }}</strong>
            </span>
            <span class="visit-strip__action">{{ nextRegistration ? '查看' : '去挂号' }}<UiIcon name="arrowRight" :size="16" /></span>
          </button>
        </div>
      </header>

      <main class="agent-home__main">
        <aside class="agent-home__rail" aria-label="常用健康服务">
          <section class="agent-panel agent-panel--actions" aria-labelledby="action-title">
            <div class="agent-panel__heading">
              <div><span>让助手来办</span><h2 id="action-title">常用任务</h2></div>
              <RouterLink to="/assistant">开始新对话<UiIcon name="arrowRight" :size="16" /></RouterLink>
            </div>
            <div class="agent-action-grid">
              <button v-for="action in agentActions" :key="action.label" type="button" @click="openAssistant(action.prompt)">
                <span><UiIcon :name="action.icon" :size="21" /></span>
                <strong>{{ action.label }}</strong>
                <UiIcon name="arrowRight" :size="15" />
              </button>
            </div>
          </section>

          <section class="agent-panel agent-panel--schedules" aria-labelledby="schedule-title">
            <div class="agent-panel__heading">
              <div><span>实时信息</span><h2 id="schedule-title">今日可预约</h2></div>
              <RouterLink to="/registration">全部号源<UiIcon name="arrowRight" :size="16" /></RouterLink>
            </div>
            <p v-if="sectionErrors.schedules" class="agent-panel__state">号源暂时无法获取，可让助手稍后再查。</p>
            <div v-else-if="availableSchedules.length" class="schedule-stack">
              <button v-for="schedule in availableSchedules" :key="schedule.id" type="button" @click="openAssistant(`帮我看看${schedule.deptName}${schedule.staffName}的可预约时间。`)">
                <span class="schedule-stack__icon"><UiIcon name="hospital" :size="18" /></span>
                <span><strong>{{ schedule.deptName }} · {{ schedule.staffName }}</strong><small>{{ formatTimePeriod(schedule.timePeriod) }} · 挂号费 ¥{{ schedule.registerFee }}</small></span>
                <b>余 {{ schedule.remainingCount }}</b>
              </button>
            </div>
            <p v-else class="agent-panel__state">今日暂无可预约号源，可让助手查询后续排班。</p>
          </section>
        </aside>
      </main>
    </div>
  </AppShell>
</template>

<style scoped>
.agent-home {
  --home-ink: #17343b;
  --home-muted: #60777d;
  --home-teal: #0f8f82;
  --home-deep: #075b55;
  --home-aqua: #dff5f2;
  min-height: 100vh;
  background: #edf6f7;
  color: var(--home-ink);
}
.agent-home__header { min-height: 258px; background: #dff3f4; }
.agent-home__header-inner { width: min(1120px, calc(100% - 64px)); margin: 0 auto; padding: 28px 0 54px; }
.agent-home__brand-row { display: none; align-items: center; justify-content: space-between; gap: 20px; }
.agent-brand { display: inline-flex; align-items: center; gap: 11px; color: var(--home-deep); text-decoration: none; }
.agent-brand__mark { width: 44px; height: 44px; display: grid; place-items: center; border-radius: 14px; background: var(--home-deep); color: #fff; box-shadow: 0 8px 22px rgba(7, 91, 85, .18); }
.agent-brand strong, .agent-brand small { display: block; }
.agent-brand strong { font-size: 19px; letter-spacing: .02em; }
.agent-brand small { margin-top: 2px; color: #4e7777; font-family: var(--font-utility); font-size: 9px; font-weight: 750; letter-spacing: .16em; }
.agent-home__emergency { min-height: 34px; display: inline-flex; align-items: center; gap: 6px; padding: 0 11px; border: 1px solid #e7caa7; border-radius: 999px; background: #fff8ef; color: #7b4d20; font-size: 12px; font-weight: 650; }
.agent-home__welcome { margin-top: 0; }
.agent-home__welcome p { margin: 0 0 5px; color: #5c7a7b; font-size: 12px; font-weight: 650; letter-spacing: .04em; }
.agent-home__welcome h1 { margin: 0; color: #153b3c; font-size: clamp(28px, 3.4vw, 43px); font-weight: 750; line-height: 1.18; letter-spacing: -.04em; }
.visit-strip { width: min(680px, 100%); min-height: 72px; display: grid; grid-template-columns: auto minmax(0,1fr) auto; align-items: center; gap: 13px; margin-top: 25px; padding: 11px 13px; border: 1px solid rgba(15, 143, 130, .2); border-radius: 18px; background: rgba(255,255,255,.82); color: inherit; cursor: pointer; text-align: left; box-shadow: 0 10px 28px rgba(27, 78, 81, .07); transition: border-color 160ms ease, box-shadow 160ms ease; }
.visit-strip:hover, .visit-strip:focus-visible { border-color: var(--home-teal); box-shadow: 0 13px 30px rgba(27, 78, 81, .12); }
.visit-strip__icon { width: 44px; height: 44px; display: grid; place-items: center; border-radius: 13px; background: var(--home-aqua); color: var(--home-teal); }
.visit-strip__body { min-width: 0; }
.visit-strip__body small, .visit-strip__body strong { display: block; }
.visit-strip__body small { margin-bottom: 4px; color: var(--home-muted); font-size: 11px; }
.visit-strip__body strong { overflow: hidden; font-size: 14px; text-overflow: ellipsis; white-space: nowrap; }
.visit-strip__action { display: inline-flex; align-items: center; gap: 2px; color: var(--home-teal); font-size: 12px; font-weight: 750; }
.agent-home__main { width: min(1120px, calc(100% - 64px)); margin: -28px auto 0; padding-bottom: 52px; }
.agent-home__rail { width: 100%; display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }
.agent-panel { padding: 21px; border: 1px solid #d5e6e6; border-radius: 22px; background: rgba(255,255,255,.92); box-shadow: 0 10px 30px rgba(25, 74, 77, .07); }
.agent-panel__heading { display: flex; align-items: end; justify-content: space-between; gap: 12px; margin-bottom: 16px; }
.agent-panel__heading span { display: block; margin-bottom: 3px; color: var(--home-teal); font-size: 10px; font-weight: 800; letter-spacing: .11em; }
.agent-panel__heading h2 { margin: 0; color: var(--home-ink); font-size: 20px; }
.agent-panel__heading a { min-height: 36px; display: inline-flex; align-items: center; gap: 2px; color: var(--home-muted); font-size: 11px; font-weight: 700; white-space: nowrap; }
.agent-action-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
.agent-action-grid button { min-width: 0; min-height: 100px; display: flex; align-items: center; flex-direction: column; justify-content: center; gap: 8px; padding: 10px 5px; border: 1px solid #d9e9e8; border-radius: 16px; background: #f7fbfb; color: var(--home-ink); cursor: pointer; transition: border-color 160ms ease, background-color 160ms ease; }
.agent-action-grid button:hover, .agent-action-grid button:focus-visible { border-color: #73bdb5; background: #eef8f7; }
.agent-action-grid button > span { width: 40px; height: 40px; display: grid; place-items: center; border-radius: 13px; background: var(--home-aqua); color: var(--home-teal); }
.agent-action-grid button strong { overflow: hidden; max-width: 100%; font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
.agent-action-grid button > svg { display: none; }
.schedule-stack { display: grid; }
.schedule-stack button { min-width: 0; min-height: 68px; display: grid; grid-template-columns: auto minmax(0,1fr) auto; align-items: center; gap: 10px; padding: 10px 0; border: 0; border-bottom: 1px solid #e1ebeb; background: transparent; color: inherit; cursor: pointer; text-align: left; }
.schedule-stack button:first-child { border-top: 1px solid #e1ebeb; }
.schedule-stack button:hover span:nth-child(2) strong, .schedule-stack button:focus-visible span:nth-child(2) strong { color: var(--home-teal); }
.schedule-stack__icon { width: 36px; height: 36px; display: grid; place-items: center; border-radius: 11px; background: #e9f6f4; color: var(--home-teal); }
.schedule-stack strong, .schedule-stack small { display: block; }
.schedule-stack strong { overflow: hidden; font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
.schedule-stack small { margin-top: 4px; color: var(--home-muted); font-size: 10px; }
.schedule-stack b { color: var(--home-teal); font-size: 11px; white-space: nowrap; }
.agent-panel__state { min-height: 74px; display: flex; align-items: center; margin: 0; color: var(--home-muted); font-size: 12px; line-height: 1.6; }
@media (max-width: 767px) {
  .agent-home { min-height: 100dvh; }
  .agent-home__header { min-height: 224px; }
  .agent-home__header-inner { width: 100%; padding: 18px 17px 46px; }
  .agent-home__brand-row { display: flex; }
  .agent-brand__mark { width: 39px; height: 39px; border-radius: 12px; }
  .agent-brand strong { font-size: 17px; }
  .agent-home__emergency { min-height: 32px; padding-inline: 9px; font-size: 10px; }
  .agent-home__welcome { margin-top: 27px; }
  .agent-home__welcome p { font-size: 11px; }
  .agent-home__welcome h1 { font-size: 27px; line-height: 1.22; }
  .visit-strip { min-height: 66px; margin-top: 20px; padding: 9px 10px; border-radius: 16px; }
  .visit-strip__icon { width: 40px; height: 40px; border-radius: 12px; }
  .visit-strip__body strong { font-size: 12px; }
  .visit-strip__action { font-size: 11px; }
  .agent-home__main { width: 100%; margin-top: -24px; padding: 0 12px 28px; }
  .agent-home__rail { grid-template-columns: 1fr; gap: 14px; }
  .agent-panel { padding: 19px 17px; border-radius: 21px; }
  .agent-panel__heading h2 { font-size: 19px; }
  .agent-action-grid button { min-height: 92px; }
}
@media (max-width: 380px) {
  .agent-home__header-inner { padding-inline: 14px; }
  .agent-home__welcome h1 { font-size: 25px; }
  .visit-strip__action { width: 18px; overflow: hidden; color: var(--home-teal); }
  .agent-home__main { padding-inline: 9px; }
}
@media (prefers-reduced-motion: reduce) {
  .visit-strip, .agent-action-grid button { transition: none; }
}
</style>
