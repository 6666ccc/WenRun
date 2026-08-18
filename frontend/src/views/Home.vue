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
const loading = ref(true)
const error = ref('')
const name = computed(() => user.value?.realName || user.value?.username || '患者')
const nextRegistration = computed(() => data.value.registrations.find((item) => item.status === 1) || data.value.registrations[0])
const pendingTotal = computed(() => data.value.pendingCharges.reduce((sum, item) => sum + Number(item.totalAmount || 0), 0))
const services = [
  { icon: 'calendar', label: '预约挂号', to: '/registration' },
  { icon: 'ai', label: '健康助手', to: '/assistant' },
  { icon: 'wallet', label: '门诊缴费', to: '/payment' },
  { icon: 'hospital', label: '科室医生', to: '/department' },
  { icon: 'record', label: '就诊记录', to: '/registration' },
  { icon: 'user', label: '我的档案', to: '/user' },
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
    <div class="home-intro">
      <div>
        <p class="eyebrow">{{ formatDate(new Date()) }}</p>
        <h1>{{ formatTime() }}，{{ name }}</h1>
      </div>
      <button class="btn btn--outline" type="button" @click="router.push('/assistant')"><UiIcon name="ai" :size="18" />健康助手</button>
    </div>

    <UiState :loading="loading" :error="error">
      <section class="next-step" aria-labelledby="next-step-title">
        <div class="next-step__label"><span class="status-dot" />下一步</div>
        <div v-if="nextRegistration || data.pendingCharges.length" class="next-step__content">
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

      <section class="home-section" aria-labelledby="services-title">
        <div class="section-heading"><div><h2 id="services-title">常用服务</h2></div></div>
        <div class="service-grid">
          <button v-for="service in services" :key="service.label" class="service-item" type="button" @click="router.push(service.to)">
            <span class="service-item__icon"><UiIcon :name="service.icon" :size="21" /></span><strong>{{ service.label }}</strong><span class="service-item__arrow" aria-hidden="true">→</span>
          </button>
        </div>
      </section>

      <div class="home-columns">
        <section class="home-section home-panel" aria-labelledby="recent-title">
          <div class="section-heading"><div><h2 id="recent-title">近期记录</h2></div><RouterLink to="/registration">查看全部</RouterLink></div>
          <div v-if="data.registrations.length" class="record-list">
            <RouterLink v-for="item in data.registrations.slice(0, 3)" :key="item.id" :to="`/registration/${item.id}`" class="record-row">
              <span class="record-row__date">{{ item.workDate?.slice(5) || '—' }}</span><span><strong>{{ item.deptName }} · {{ item.staffName }}</strong><small>{{ formatVisitSchedule(item.workDate, item.timePeriod) }}</small></span><span class="record-row__status">{{ item.status === 1 ? '待就诊' : item.status === 2 ? '已就诊' : '已取消' }}</span>
            </RouterLink>
          </div>
          <p v-else class="empty-copy">暂无记录</p>
        </section>
        <section class="home-section home-panel" aria-labelledby="schedule-title">
          <div class="section-heading"><div><h2 id="schedule-title">今日可预约</h2></div><RouterLink to="/department">查看科室</RouterLink></div>
          <div v-if="data.schedules.length" class="schedule-list">
            <div v-for="schedule in data.schedules.slice(0, 4)" :key="schedule.id" class="schedule-row"><span><strong>{{ schedule.deptName }}</strong><small>{{ schedule.staffName }} · {{ formatTimePeriod(schedule.timePeriod) }}</small></span><span><b>余号 {{ schedule.remainingCount }}</b><small>¥{{ schedule.registerFee }}</small></span></div>
          </div>
          <p v-else class="empty-copy">暂无号源</p>
        </section>
      </div>
    </UiState>
  </AppShell>
</template>

<style scoped>
.home-intro{display:flex;align-items:flex-start;justify-content:space-between;gap:24px;margin-bottom:24px}.home-intro h1{margin:5px 0 6px;font-size:28px}.home-intro>div>p:last-child{color:var(--color-text-secondary);margin:0}.eyebrow{margin:0;color:var(--color-brand-700);font-size:12px;font-weight:700;letter-spacing:.08em}.next-step{padding:22px 24px;background:var(--color-surface);border:1px solid var(--color-border);border-radius:16px;box-shadow:0 12px 28px rgba(0,122,104,.08)}.next-step__label{display:flex;align-items:center;gap:8px;color:var(--color-brand-700);font-size:14px;font-weight:700}.status-dot{width:8px;height:8px;border-radius:50%;background:var(--color-mint-500);box-shadow:0 0 0 4px var(--color-mint-100)}.next-step__content{display:flex;align-items:center;justify-content:space-between;gap:24px;margin-top:14px}.next-step h2{margin:0 0 4px;font-size:20px}.next-step p{margin:0;color:var(--color-text-secondary)}.next-step__secondary{margin-top:16px;padding-top:14px;border-top:1px solid var(--color-border);font-size:14px}.next-step__secondary button{padding:0;border:0;background:none;color:var(--color-brand-700);cursor:pointer;font:inherit;font-weight:600}.home-section{margin-top:32px}.section-heading{display:flex;justify-content:space-between;align-items:end;gap:16px;margin-bottom:14px}.section-heading h2{margin:3px 0 0;font-size:20px}.section-heading a{color:var(--color-brand-700);font-size:14px}.service-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.service-item{display:flex;align-items:center;gap:12px;min-height:88px;padding:16px;border:1px solid var(--color-border);border-radius:14px;background:var(--color-surface);color:var(--color-text);cursor:pointer;text-align:left;transition:border-color .16s,box-shadow .16s,transform .16s}.service-item:hover,.service-item:focus-visible{border-color:var(--color-brand-600);box-shadow:0 8px 20px rgba(0,122,104,.08);transform:translateY(-1px)}.service-item__icon{display:grid;place-items:center;width:42px;height:42px;flex:0 0 42px;border-radius:12px;background:var(--color-mint-100);color:var(--color-brand-700)}.service-item strong,.service-item small{display:block}.service-item strong{font-size:15px}.service-item small{margin-top:3px;color:var(--color-text-secondary);font-size:13px}.service-item__arrow{margin-left:auto;color:var(--color-brand-700);font-size:20px}.home-columns{display:grid;grid-template-columns:1fr 1fr;gap:20px}.home-panel{min-width:0}.record-list,.schedule-list{border-top:1px solid var(--color-border)}.record-row,.schedule-row{display:flex;align-items:center;gap:12px;min-height:68px;padding:10px 0;border-bottom:1px solid var(--color-border);text-decoration:none;color:inherit}.record-row__date{font-size:18px;font-weight:700;color:var(--color-text-secondary)}.record-row>span:nth-child(2),.schedule-row>span:first-child{min-width:0;flex:1}.record-row strong,.record-row small,.schedule-row strong,.schedule-row small{display:block}.record-row small,.schedule-row small{margin-top:3px;color:var(--color-text-secondary);font-size:13px}.record-row__status,.schedule-row b{color:var(--color-brand-700);font-size:13px;white-space:nowrap}.schedule-row>span:last-child{text-align:right}.empty-copy{padding:24px 0;color:var(--color-text-secondary);font-size:14px}@media(max-width:900px){.service-grid{grid-template-columns:repeat(2,1fr)}.home-columns{grid-template-columns:1fr}}@media(max-width:767px){.home-intro{display:block}.home-intro .btn{width:100%;margin-top:16px}.home-intro h1{font-size:24px}.next-step__content{display:block}.next-step__content .btn{width:100%;margin-top:16px}.service-grid{gap:8px}.service-item{min-height:108px;padding:14px 12px;align-items:flex-start}.service-item__arrow{display:none}.service-item small{font-size:12px}.home-section{margin-top:24px}}
</style>
<style scoped>
.service-item { transition: border-color .16s, background-color .16s, box-shadow .16s; }
.service-item:hover, .service-item:focus-visible { transform: none; box-shadow: 0 4px 12px rgba(0,122,104,.06); }
</style>
