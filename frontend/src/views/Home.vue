<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth } from '../stores'
import { listCharges, listRegistrations, listSchedules } from '../api'
import { formatDate, formatTime, formatTimePeriod, formatVisitSchedule } from '../utils'
import { listVisits } from '../api/modules/consultation'
import { MODE_AGENT, writeMode } from '../features/experience/mode'
import AppShell from '../components/AppShell.vue'
import UiIcon from '../components/UiIcon.vue'
import UiState from '../components/UiState.vue'

const router = useRouter()
const { user } = useAuth()
const data = ref({ registrations: [], pendingCharges: [], schedules: [], visits: [] })
const loading = ref(true)
const error = ref('')
const name = computed(() => user.value?.realName || user.value?.username || '患者')
const actions = [
  { icon: 'calendar', label: '预约挂号', to: '/registration', color: '#3d5a5c' },
  { icon: 'hospital', label: '科室浏览', to: '/department', color: '#3d5a5c' },
  { icon: 'wallet', label: '门诊缴费', to: '/payment', color: '#c8944a' },
  { icon: 'record', label: '我的病历', to: '/user', color: '#7a9e85' },
  { icon: 'ai', label: 'AI 助手', to: '/assistant', color: '#5a8590' },
  { icon: 'user', label: '个人中心', to: '/user', color: '#8c8278' },
]
const stats = computed(() => [
  { icon: 'calendar', label: '我的挂号', value: data.value.registrations.length, color: '#3d5a5c' },
  { icon: 'hourglass', label: '待缴费', value: data.value.pendingCharges.length, color: '#c8944a' },
  { icon: 'hospital', label: '今日可挂号科室', value: data.value.schedules.length, color: '#7a9e85' },
  { icon: 'record', label: '就诊记录', value: data.value.visits.length, color: '#5a8590' },
])

onMounted(async () => {
  if (!user.value?.userId) return void (loading.value = false)
  const [registrations, charges, schedules, visits] = await Promise.allSettled([
    listRegistrations({ userId: user.value.userId }),
    listCharges({ patientId: user.value.patientId }),
    listSchedules({ workDate: new Date().toISOString().slice(0, 10) }),
    listVisits({ patientId: user.value.patientId }),
  ])
  const value = (result) => result.status === 'fulfilled' && Array.isArray(result.value) ? result.value : []
  data.value = {
    registrations: value(registrations),
    pendingCharges: value(charges).filter((charge) => charge.payStatus === 0),
    schedules: value(schedules),
    visits: value(visits),
  }
  if ([registrations, charges, schedules].every((result) => result.status === 'rejected')) error.value = '首页数据加载失败'
  loading.value = false
})

function go(action) {
  if (action.to === '/assistant') writeMode(MODE_AGENT)
  router.push(action.to)
}
</script>

<template>
  <AppShell>
    <div class="view-hero">
      <h2 class="view-hero__greeting">{{ formatTime() }}，{{ name }}</h2>
      <p class="view-hero__date">{{ formatDate(new Date()) }}</p>
      <div class="view-hero__tag"><span class="view-hero__tag-dot" />温润诊所 · 祝您安康</div>
    </div>
    <div class="view-quick-grid">
      <button v-for="(action,index) in actions" :key="action.label" class="view-quick-item" :style="{ animationDelay: `${index * 60}ms` }" @click="go(action)">
        <div class="view-quick-item__icon" :style="{ background: `${action.color}12`, color: action.color }"><UiIcon :name="action.icon" :size="22" /></div>
        <span class="view-quick-item__label">{{ action.label }}</span>
      </button>
    </div>
    <UiState :loading="loading" :error="error">
      <div class="vue-stats stagger">
        <div v-for="stat in stats" :key="stat.label" class="card view-stat-card">
          <div class="vue-stat-icon" :style="{ color: stat.color, background: `${stat.color}14` }"><UiIcon :name="stat.icon" :size="22" /></div>
          <div><small>{{ stat.label }}</small><div class="view-stat-card__value">{{ stat.value }}</div></div>
        </div>
      </div>
      <div class="vue-home-grid stagger">
        <section class="card">
          <div class="flex-between mb-md"><h3>我的挂号</h3><button class="btn btn--accent btn--sm" @click="router.push('/registration')">预约挂号</button></div>
          <div v-if="data.registrations.length">
            <div v-for="item in data.registrations.slice(0,5)" :key="item.id" class="view-list-row">
              <div><strong>{{ item.deptName }} · {{ item.staffName }}</strong><div class="text-sub text-sm">{{ formatVisitSchedule(item.workDate, item.timePeriod) }}</div></div>
              <span class="shared-status" :class="item.status === 1 ? 'shared-status--pending' : item.status === 2 ? 'shared-status--active' : 'shared-status--cancelled'">{{ item.status === 1 ? '已挂号' : item.status === 2 ? '已就诊' : '已退号' }}</span>
            </div>
          </div><p v-else class="vue-empty">暂无挂号记录</p>
        </section>
        <section class="card">
          <div class="flex-between mb-md"><h3>待缴费</h3><button class="btn btn--outline btn--sm" @click="router.push('/payment')">全部 →</button></div>
          <div v-if="data.pendingCharges.length">
            <div v-for="charge in data.pendingCharges.slice(0,5)" :key="charge.id" class="view-list-row">
              <div><strong>{{ charge.orderNo }}</strong><div class="text-sub text-sm">{{ formatDate(charge.createTime) }}</div></div>
              <button class="btn btn--primary btn--sm" @click="router.push(`/payment/${charge.id}`)">¥{{ Number(charge.totalAmount).toFixed(2) }} · 支付</button>
            </div>
          </div><p v-else class="vue-empty">暂无待缴费项目</p>
        </section>
      </div>
      <section v-if="data.schedules.length" class="card mt-lg">
        <h3>今日可挂号</h3>
        <div class="vue-schedules"><div v-for="schedule in data.schedules" :key="schedule.id"><strong>{{ schedule.deptName }}</strong><span>{{ schedule.staffName }} · {{ formatTimePeriod(schedule.timePeriod) }}</span><b>余号 {{ schedule.remainingCount }} · ¥{{ schedule.registerFee }}</b></div></div>
      </section>
    </UiState>
  </AppShell>
</template>

<style scoped>
.view-quick-item{border:0;text-align:inherit}.vue-stats{display:flex;gap:16px;margin-bottom:28px;flex-wrap:wrap}.vue-stats .card{display:flex;align-items:center;gap:14px;min-width:180px}.vue-stat-icon{width:48px;height:48px;border-radius:var(--radius);display:grid;place-items:center}.vue-stats small{color:var(--c-sub)}
.vue-home-grid{display:grid;grid-template-columns:1fr 1fr;gap:20px}.vue-home-grid h3,.vue-schedules+h3{margin:0}.vue-empty{text-align:center;padding:24px;color:var(--c-muted);font-size:.85rem}.vue-schedules{display:flex;gap:16px;flex-wrap:wrap}.vue-schedules>div{padding:14px 20px;background:var(--c-bg);border:1px solid var(--c-border-light);border-radius:var(--radius);min-width:200px}.vue-schedules strong,.vue-schedules span,.vue-schedules b{display:block}.vue-schedules span{color:var(--c-sub);font-size:.85rem}.vue-schedules b{color:var(--c-accent);font-size:.85rem;margin-top:6px}
@media(max-width:1023px){.vue-stats{display:none}.vue-home-grid{grid-template-columns:1fr;gap:12px}.vue-schedules{flex-direction:column}.view-hero{display:block}}
</style>
