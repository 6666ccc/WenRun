<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth } from '../stores'
import { listCharges, listRegistrations, listSchedules } from '../api'
import { listVisits } from '../api/modules/consultation'
import { formatDate, formatTime, formatTimePeriod, formatVisitSchedule } from '../utils'
import AppShell from '../components/AppShell.vue'
import UiIcon from '../components/UiIcon.vue'
import UiState from '../components/UiState.vue'

const router = useRouter()
const { user } = useAuth()
const data = ref({ registrations: [], pendingCharges: [], schedules: [], visits: [] })
const sectionErrors = ref({ registrations: false, charges: false, schedules: false, visits: false })
const loading = ref(true)
const error = ref('')
const name = computed(() => user.value?.realName || user.value?.username || '患者')
const nextRegistration = computed(() => data.value.registrations.find((item) => item.status === 1))
const nextStepUnavailable = computed(() => sectionErrors.value.registrations || sectionErrors.value.charges)
const pendingTotal = computed(() => data.value.pendingCharges.reduce((sum, item) => sum + Number(item.totalAmount || 0), 0))
const services = [
  { icon: 'calendar', label: '预约挂号', description: '按科室与时段选择号源', to: '/registration' },
  { icon: 'ai', label: '健康助手', description: '查询健康信息与就医事项', to: '/assistant' },
  { icon: 'wallet', label: '门诊缴费', description: '查看账单与缴费状态', to: '/payment' },
  { icon: 'hospital', label: '科室医生', description: '浏览科室和医生团队', to: '/department' },
  { icon: 'record', label: '就诊记录', description: '回看预约与就诊信息', to: '/registration' },
  { icon: 'user', label: '我的档案', description: '维护患者与联系信息', to: '/user' },
]

onMounted(async () => {
  if (!user.value?.userId) return void (loading.value = false)
  const results = await Promise.allSettled([
    listRegistrations({ userId: user.value.userId }),
    listCharges({ patientId: user.value.patientId }),
    listSchedules({ workDate: new Date().toISOString().slice(0, 10) }),
    listVisits({ patientId: user.value.patientId }),
  ])
  const value = (result) => result.status === 'fulfilled' && Array.isArray(result.value) ? result.value : []
  sectionErrors.value = {
    registrations: results[0].status === 'rejected',
    charges: results[1].status === 'rejected',
    schedules: results[2].status === 'rejected',
    visits: results[3].status === 'rejected',
  }
  data.value = {
    registrations: value(results[0]),
    pendingCharges: value(results[1]).filter((charge) => charge.payStatus === 0),
    schedules: value(results[2]),
    visits: value(results[3]),
  }
  if (results.every((result) => result.status === 'rejected')) error.value = '首页数据加载失败，请稍后重试'
  loading.value = false
})
</script>

<template>
  <AppShell>
    <div class="home-intro home-reveal home-reveal--intro">
      <div>
        <p class="eyebrow">{{ formatDate(new Date()) }}</p>
        <h1>{{ formatTime() }}，{{ name }}</h1>
      </div>
    </div>

    <UiState :loading="loading" :error="error">
      <section class="next-step home-reveal home-reveal--next" aria-labelledby="next-step-title">
        <div class="next-step__label"><span class="status-dot" /><strong>下一步</strong></div>
        <div v-if="nextStepUnavailable" class="next-step__content">
          <div><h2 id="next-step-title">行程信息暂时无法获取</h2><p>您仍可进入挂号或缴费服务继续办理</p></div>
          <button class="btn btn--outline" type="button" @click="router.push('/registration')">前往挂号服务</button>
        </div>
        <div v-else-if="nextRegistration || data.pendingCharges.length" class="next-step__content">
          <div v-if="nextRegistration">
            <h2 id="next-step-title">{{ nextRegistration.deptName }} · {{ nextRegistration.staffName }}</h2>
            <p>{{ formatVisitSchedule(nextRegistration.workDate, nextRegistration.timePeriod) }}</p>
          </div>
          <div v-else>
            <h2 id="next-step-title">还有 {{ data.pendingCharges.length }} 笔费用待处理</h2>
            <p>合计 ¥{{ pendingTotal.toFixed(2) }}</p>
          </div>
          <button class="btn btn--primary" type="button" @click="router.push(nextRegistration ? `/registration/${nextRegistration.id}` : '/payment')">{{ nextRegistration ? '查看挂号详情' : '查看并支付' }}</button>
        </div>
        <div v-else class="next-step__content">
          <div><h2 id="next-step-title">还没有预约</h2><p>选择科室和时段</p></div>
          <button class="btn btn--primary" type="button" @click="router.push('/registration')">开始挂号</button>
        </div>
        <p v-if="nextRegistration && data.pendingCharges.length" class="next-step__secondary">另有 {{ data.pendingCharges.length }} 笔待缴费用，共 ¥{{ pendingTotal.toFixed(2) }} · <button type="button" @click="router.push('/payment')">去处理</button></p>
      </section>

      <section class="home-section home-reveal home-reveal--services" aria-labelledby="services-title">
        <div class="section-heading"><div><h2 id="services-title">常用服务</h2></div></div>
        <div class="service-grid stagger">
          <article v-for="service in services" :key="service.label" class="service-item">
            <span class="service-item__icon"><UiIcon :name="service.icon" :size="21" /></span>
            <div class="service-item__body"><RouterLink :to="service.to"><strong>{{ service.label }}</strong></RouterLink><p>{{ service.description }}</p></div>
            <span class="service-item__arrow"><UiIcon name="arrowRight" :size="18" /></span>
          </article>
        </div>
      </section>

      <div class="home-columns home-reveal home-reveal--panels">
        <section class="home-section home-panel" aria-labelledby="recent-title">
          <div class="section-heading"><div><h2 id="recent-title">近期记录</h2></div><RouterLink to="/registration">查看全部</RouterLink></div>
          <p v-if="sectionErrors.registrations" class="section-error">近期记录暂时无法获取</p>
          <div v-else-if="data.registrations.length" class="record-list">
            <RouterLink v-for="item in data.registrations.slice(0, 3)" :key="item.id" :to="`/registration/${item.id}`" class="record-row">
              <span class="record-row__date">{{ item.workDate?.slice(5) || '—' }}</span><span><strong>{{ item.deptName }} · {{ item.staffName }}</strong><small>{{ formatVisitSchedule(item.workDate, item.timePeriod) }}</small></span><span class="record-row__status">{{ item.status === 1 ? '待就诊' : item.status === 2 ? '已就诊' : '已取消' }}</span>
            </RouterLink>
          </div>
          <p v-else class="empty-copy">暂无记录</p>
        </section>
        <section class="home-section home-panel" aria-labelledby="schedule-title">
          <div class="section-heading"><div><h2 id="schedule-title">今日可预约</h2></div><RouterLink to="/department">查看科室</RouterLink></div>
          <p v-if="sectionErrors.schedules" class="section-error">今日号源暂时无法获取</p>
          <div v-else-if="data.schedules.length" class="schedule-list">
            <div v-for="schedule in data.schedules.slice(0, 4)" :key="schedule.id" class="schedule-row"><span><strong>{{ schedule.deptName }}</strong><small>{{ schedule.staffName }} · {{ formatTimePeriod(schedule.timePeriod) }}</small></span><span><b>余号 {{ schedule.remainingCount }}</b><small>¥{{ schedule.registerFee }}</small></span></div>
          </div>
          <p v-else class="empty-copy">暂无号源</p>
        </section>
      </div>
    </UiState>
  </AppShell>
</template>

<style scoped>
.home-intro { margin-bottom: 30px; }
.home-intro h1 { margin: 7px 0 0; font-size: clamp(34px, 3.4vw, 46px); line-height: 1.18; letter-spacing: -.045em; }
.eyebrow { margin: 0; color: var(--color-brand-700); font-family: var(--font-utility); font-size: 13px; font-weight: 750; letter-spacing: .09em; }

.next-step {
  min-height: 108px;
  display: grid;
  grid-template-columns: 164px minmax(0, 1fr);
  overflow: hidden;
  border: 1px solid var(--color-border);
  border-radius: 15px;
  background: var(--color-surface);
  box-shadow: var(--shadow-sm);
}
.next-step__label {
  display: flex;
  align-items: center;
  gap: 13px;
  padding: 26px 22px;
  background: var(--color-brand-900);
  color: #fff;
}
.next-step__label strong { color: #fff; font-size: 16px; }
.status-dot {
  width: 10px;
  height: 10px;
  flex: 0 0 10px;
  border-radius: 50%;
  background: #9de2d6;
  box-shadow: 0 0 0 5px rgba(157,226,214,.14);
  animation: home-status-pulse 2.8s var(--ease-standard) infinite;
}
.next-step__content { display: flex; align-items: center; justify-content: space-between; gap: 28px; min-width: 0; padding: 25px 28px; }
.next-step h2 { margin: 0 0 6px; font-size: 22px; line-height: 1.3; }
.next-step p { margin: 0; color: var(--color-text-secondary); font-size: 14px; }
.next-step__secondary { grid-column: 2; margin: 0; padding: 0 28px 19px; color: var(--color-text-secondary); font-size: 14px; }
.next-step__secondary button { min-height: 34px; padding: 0 3px; border: 0; background: none; color: var(--color-brand-700); cursor: pointer; font: inherit; font-weight: 750; }

.home-section { margin-top: 30px; }
.section-heading { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 17px; }
.section-heading h2 { margin: 0; font-size: 22px; letter-spacing: -.02em; }
.section-heading a { min-height: 40px; display: inline-flex; align-items: center; color: var(--color-brand-700); font-size: 14px; font-weight: 750; }

.service-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
.service-item {
  position: relative;
  min-height: 116px;
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px;
  border: 1px solid var(--color-border);
  border-radius: 14px;
  background: var(--color-surface);
  color: var(--color-text);
  transition: border-color 180ms var(--ease-standard), box-shadow 180ms var(--ease-standard), transform 180ms var(--ease-standard);
}
.service-item:hover, .service-item:has(a:focus-visible) { border-color: var(--color-brand-600); box-shadow: 0 12px 28px rgba(7,63,59,.09); transform: translateY(-2px); }
.service-item:has(a:focus-visible) { outline: 3px solid var(--color-focus); outline-offset: 3px; }
.service-item__icon {
  width: 48px;
  height: 48px;
  display: grid;
  place-items: center;
  flex: 0 0 48px;
  border: 1px solid #cbe7e2;
  border-radius: 13px;
  background: var(--color-mint-100);
  color: var(--color-brand-700);
  transition: transform 180ms var(--ease-standard), background-color 180ms var(--ease-standard);
}
.service-item:hover .service-item__icon, .service-item:has(a:focus-visible) .service-item__icon { background: #d9efeb; transform: scale(1.04); }
.service-item__body { min-width: 0; }
.service-item__body a { color: var(--color-text); text-decoration: none; }
.service-item__body a::after { content: ''; position: absolute; inset: 0; border-radius: inherit; }
.service-item__body a:focus-visible { outline: 0; box-shadow: none; }
.service-item strong { display: block; font-size: 16px; }
.service-item p { margin: 5px 0 0; color: var(--color-text-secondary); font-size: 14px; line-height: 1.5; }
.service-item__arrow { display: grid; place-items: center; margin-left: auto; color: var(--color-brand-700); transition: transform 180ms var(--ease-standard); }
.service-item:hover .service-item__arrow, .service-item:has(a:focus-visible) .service-item__arrow { transform: translateX(4px); }

.home-columns { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-top: 30px; }
.home-columns .home-section { margin-top: 0; }
.home-panel { min-width: 0; padding: 24px 24px 10px; border: 1px solid var(--color-border); border-radius: 15px; background: var(--color-surface); box-shadow: var(--shadow-xs); }
.record-list, .schedule-list { border-top: 1px solid var(--color-border); }
.record-row, .schedule-row { min-height: 72px; display: flex; align-items: center; gap: 14px; margin: 0 -8px; padding: 12px 8px; border-bottom: 1px solid var(--color-border); border-radius: 8px; color: inherit; text-decoration: none; transition: background-color 180ms var(--ease-standard), padding-left 180ms var(--ease-standard); }
.record-row:hover, .record-row:focus-visible { padding-left: 12px; background: var(--color-mint-050); }
.record-row__date { color: var(--color-text-secondary); font-family: var(--font-utility); font-size: 18px; font-weight: 750; }
.record-row > span:nth-child(2), .schedule-row > span:first-child { min-width: 0; flex: 1; }
.record-row strong, .record-row small, .schedule-row strong, .schedule-row small { display: block; }
.record-row strong, .schedule-row strong { font-size: 15px; }
.record-row small, .schedule-row small { margin-top: 3px; color: var(--color-text-secondary); font-size: 13px; }
.record-row__status, .schedule-row b { color: var(--color-brand-700); font-size: 13px; white-space: nowrap; }
.schedule-row > span:last-child { text-align: right; }
.empty-copy, .section-error { min-height: 70px; display: flex; align-items: center; margin: 0; padding: 14px 0; color: var(--color-text-secondary); font-size: 14px; }
.section-error { color: var(--color-danger); }

.home-reveal { animation: home-reveal 360ms var(--ease-enter) both; }
.home-reveal--intro { animation-delay: 20ms; }
.home-reveal--next { animation-delay: 75ms; }
.home-reveal--services { animation-delay: 130ms; }
.home-reveal--panels { animation-delay: 185ms; }

@keyframes home-reveal {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}
@keyframes home-status-pulse {
  0%, 100% { box-shadow: 0 0 0 4px rgba(157,226,214,.1); }
  50% { box-shadow: 0 0 0 8px rgba(157,226,214,.2); }
}

@media (max-width: 1040px) {
  .service-grid { grid-template-columns: repeat(2, 1fr); }
  .home-columns { grid-template-columns: 1fr; }
}
@media (max-width: 767px) {
  .home-intro { margin-bottom: 24px; }
  .home-intro h1 { font-size: 30px; }
  .next-step { grid-template-columns: 1fr; }
  .next-step__label { min-height: 58px; padding: 14px 18px; }
  .next-step__content { display: block; padding: 20px 18px; }
  .next-step__content .btn { width: 100%; margin-top: 17px; }
  .next-step__secondary { grid-column: 1; padding: 0 18px 17px; }
  .home-section, .home-columns { margin-top: 26px; }
  .service-grid { gap: 10px; }
  .service-item { min-height: 112px; padding: 16px; }
  .service-item p { font-size: 13px; }
  .service-item__arrow { display: none; }
  .home-panel { padding: 20px 17px 8px; }
}
@media (max-width: 479px) {
  .service-grid { grid-template-columns: 1fr; }
  .service-item { min-height: 96px; }
}
@media (prefers-reduced-motion: reduce) {
  .home-reveal, .status-dot { animation: none; }
  .service-item, .service-item__icon, .service-item__arrow, .record-row, .schedule-row { transition: none; }
}
</style>
