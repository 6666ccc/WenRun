<script setup>
import { onMounted, ref } from 'vue'
import { useAuth } from '../store'
import { cancelRegistration, createRegistration, listRegistrations, listSchedules } from '../api'
import { REG_STATUS_MAP, formatDateTime, formatMoney, formatTimePeriod, formatVisitSchedule } from '../utils'
import AppShell from '../components/AppShell.vue'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import PageHeader from '../components/PageHeader.vue'
import StatusBadge from '../components/StatusBadge.vue'
import UiState from '../components/UiState.vue'

const { user } = useAuth()
const registrations = ref([])
const schedules = ref([])
const selected = ref(null)
const loading = ref(true)
const schedulesLoading = ref(false)
const booking = ref(false)
const error = ref('')
const message = ref('')
const showBook = ref(false)
const cancelState = ref({ show: false, id: null, regNo: '', loading: false })

async function load() {
  if (!user.value?.userId) return void (loading.value = false)
  loading.value = true
  try { registrations.value = await listRegistrations({ userId: user.value.userId }) || [] }
  catch (nextError) { error.value = nextError.message || '加载失败' }
  finally { loading.value = false }
}
onMounted(load)

async function openBook() {
  showBook.value = true
  schedulesLoading.value = true
  try {
    const list = await listSchedules({ workDate: new Date().toISOString().slice(0, 10) })
    schedules.value = (list || []).filter((item) => item.remainingCount > 0)
  } catch { schedules.value = [] }
  finally { schedulesLoading.value = false }
}
async function book() {
  if (!selected.value || !user.value?.patientId) return
  booking.value = true
  try {
    await createRegistration({ patientId: user.value.patientId, scheduleId: selected.value.id })
    showBook.value = false; selected.value = null; message.value = '挂号成功'
    await load()
  } catch (nextError) { message.value = nextError.message || '挂号失败' }
  finally { booking.value = false }
}
async function cancel() {
  cancelState.value.loading = true
  try { await cancelRegistration(cancelState.value.id); cancelState.value.show = false; await load() }
  catch (nextError) { error.value = nextError.message || '取消失败'; cancelState.value.loading = false }
}
</script>

<template>
  <AppShell>
    <PageHeader title="预约挂号" subtitle="查看挂号记录，预约新的门诊"><button class="btn btn--accent" @click="openBook">预约挂号</button></PageHeader>
    <div v-if="message" class="card mb-md vue-message" :class="{ success: message.includes('成功') }">{{ message }}</div>
    <UiState :loading="loading" :error="error" :empty="!registrations.length" empty-text="暂无挂号记录">
      <div class="view-table-wrap vue-reg-table">
        <table class="view-table">
          <thead><tr><th>挂号编号</th><th>患者</th><th>科室 / 医生</th><th>就诊时间</th><th>挂号时间</th><th>挂号费</th><th>状态</th><th>操作</th></tr></thead>
          <tbody><tr v-for="item in registrations" :key="item.id">
            <td>{{ item.regNo }}</td><td>{{ item.patientName }}</td><td>{{ item.deptName }} · {{ item.staffName }}</td><td>{{ formatVisitSchedule(item.workDate,item.timePeriod) }}</td><td>{{ formatDateTime(item.regTime) }}</td><td>{{ formatMoney(item.regFee) }}</td>
            <td><StatusBadge :status="item.status" :map="REG_STATUS_MAP" /></td>
            <td><div class="vue-actions"><RouterLink :to="`/registration/${item.id}`" class="btn btn--outline btn--sm">详情</RouterLink><button v-if="item.status===1" class="btn btn--danger btn--sm" @click="cancelState={show:true,id:item.id,regNo:item.regNo,loading:false}">取消</button></div></td>
          </tr></tbody>
        </table>
      </div>
      <div class="vue-reg-cards">
        <article v-for="item in registrations" :key="item.id" class="card">
          <div class="flex-between mb-sm"><strong>{{ item.deptName }}</strong><StatusBadge :status="item.status" :map="REG_STATUS_MAP" /></div>
          <p>患者：{{ item.patientName }}</p><p>医生：{{ item.staffName }}</p><p>就诊时间：{{ formatVisitSchedule(item.workDate,item.timePeriod) }}</p><p>挂号费：{{ formatMoney(item.regFee) }}</p>
          <div class="vue-actions"><RouterLink :to="`/registration/${item.id}`" class="btn btn--outline btn--sm">查看详情</RouterLink><button v-if="item.status===1" class="btn btn--danger btn--sm" @click="cancelState={show:true,id:item.id,regNo:item.regNo,loading:false}">取消挂号</button></div>
        </article>
      </div>
    </UiState>
    <div v-if="showBook" class="shared-dialog-overlay" @click="showBook=false"><div class="shared-dialog vue-book" @click.stop>
      <h3>预约挂号</h3><p class="text-sub text-sm">选择今日排班进行挂号</p>
      <div v-if="schedulesLoading" class="shared-loading"><div class="shared-loading__spinner" /></div>
      <div v-else class="vue-options"><button v-for="schedule in schedules" :key="schedule.id" :class="{ selected: selected?.id===schedule.id }" @click="selected=schedule"><strong>{{ schedule.deptName }} · {{ schedule.staffName }}</strong><span>{{ formatTimePeriod(schedule.timePeriod) }} · 余号 {{ schedule.remainingCount }} · 挂号费 ¥{{ schedule.registerFee }}</span></button><p v-if="!schedules.length">今日暂无排班</p></div>
      <div class="shared-dialog__actions"><button class="btn btn--ghost" @click="showBook=false">取消</button><button class="btn btn--primary" :disabled="booking || !selected" @click="book">{{ booking ? '挂号中…' : '确认挂号' }}</button></div>
    </div></div>
    <ConfirmDialog :show="cancelState.show" title="取消挂号" :message="`确认取消挂号单 ${cancelState.regNo}？`" :loading="cancelState.loading" @confirm="cancel" @cancel="cancelState.show=false" />
  </AppShell>
</template>

<style scoped>
.vue-message{text-align:center;color:var(--c-danger)}.vue-message.success{color:var(--c-success)}.vue-actions{display:flex;gap:6px}.vue-reg-cards{display:none}.vue-reg-cards p{color:var(--c-sub);font-size:.85rem;margin:4px 0}.vue-book{max-width:480px;max-height:80vh;overflow:auto}.vue-options{display:flex;flex-direction:column;gap:8px}.vue-options button{text-align:left;padding:12px;border:1px solid var(--c-border);border-radius:var(--radius);background:var(--c-bg)}.vue-options button.selected{border-color:var(--c-accent);background:var(--c-accent-soft)}.vue-options strong,.vue-options span{display:block}.vue-options span{font-size:.8rem;color:var(--c-sub)}
@media(max-width:800px){.vue-reg-table{display:none}.vue-reg-cards{display:flex;flex-direction:column;gap:12px}}
</style>
