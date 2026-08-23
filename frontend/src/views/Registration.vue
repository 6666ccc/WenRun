<script setup>
import { onMounted, ref } from 'vue'
import { useAuth } from '../stores'
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
const successBooking = ref(null)
const showBook = ref(false)
const reviewing = ref(false)
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
  reviewing.value = false
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
    successBooking.value = { ...selected.value }
    showBook.value = false; reviewing.value = false; selected.value = null; message.value = '挂号成功'
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
    <section v-if="message" class="card mb-md vue-message" :class="{ success: message.includes('成功') }" role="status"><strong>{{ message }}</strong><template v-if="successBooking"><p>{{ successBooking.deptName }} · {{ successBooking.staffName }}</p><p>{{ successBooking.workDate }} · {{ formatTimePeriod(successBooking.timePeriod) }} · 挂号费 ¥{{ successBooking.registerFee }}</p><div class="vue-success-actions"><RouterLink v-if="registrations[0]" class="btn btn--primary btn--sm" :to="`/registration/${registrations[0].id}`">查看挂号详情</RouterLink><RouterLink class="btn btn--outline btn--sm" to="/home">返回首页</RouterLink></div></template></section>
    <UiState :loading="loading" :error="error" :empty="!registrations.length" empty-text="暂无挂号记录">
      <div class="clinic-panel">
        <div class="clinic-panel__head">挂号记录</div>
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
      </div>
    </UiState>
    <div v-if="showBook" class="shared-dialog-overlay" role="presentation" @click="showBook=false"><div class="shared-dialog vue-book" role="dialog" aria-modal="true" aria-labelledby="booking-title" @click.stop>
      <div class="step-flow" aria-label="预约挂号流程"><span class="is-complete">1 选择号源</span><span :class="{ 'is-active': reviewing }">2 核对确认</span><span>3 完成</span></div>
      <h3 id="booking-title">{{ reviewing ? '核对挂号信息' : '预约挂号' }}</h3><p class="text-sub text-sm">{{ reviewing ? '请确认以下信息，提交后将创建挂号记录。' : '当前仅显示今日有数据的排班，不展示未返回的号源。' }}</p>
      <div v-if="schedulesLoading" class="shared-loading"><div class="shared-loading__spinner" /></div>
      <div v-else-if="!reviewing" class="vue-options"><button v-for="schedule in schedules" :key="schedule.id" type="button" :class="{ selected: selected?.id===schedule.id }" @click="selected=schedule"><strong>{{ schedule.deptName }} · {{ schedule.staffName }}</strong><span>{{ formatTimePeriod(schedule.timePeriod) }} · 余号 {{ schedule.remainingCount }} · 挂号费 ¥{{ schedule.registerFee }}</span></button><p v-if="!schedules.length">今日暂无排班</p></div>
      <dl v-else class="booking-review"><div><dt>患者</dt><dd>{{ user?.realName || user?.username || '当前患者' }}</dd></div><div><dt>科室 / 医生</dt><dd>{{ selected.deptName }} · {{ selected.staffName }}</dd></div><div><dt>日期 / 时段</dt><dd>{{ selected.workDate }} · {{ formatTimePeriod(selected.timePeriod) }}</dd></div><div><dt>挂号费</dt><dd>¥{{ selected.registerFee }}</dd></div><div><dt>余号</dt><dd>{{ selected.remainingCount }}</dd></div></dl>
      <div class="shared-dialog__actions"><button class="btn btn--ghost" type="button" @click="reviewing ? reviewing=false : showBook=false">{{ reviewing ? '返回修改' : '取消' }}</button><button v-if="!reviewing" class="btn btn--primary" type="button" :disabled="!selected" @click="reviewing=true">继续核对</button><button v-else class="btn btn--primary" type="button" :disabled="booking" @click="book">{{ booking ? '提交中…' : `确认挂号 ¥${selected.registerFee}` }}</button></div>
    </div></div>
    <ConfirmDialog :show="cancelState.show" title="取消挂号" :message="`确认取消挂号单 ${cancelState.regNo}？`" :loading="cancelState.loading" @confirm="cancel" @cancel="cancelState.show=false" />
  </AppShell>
</template>

<style scoped>
.vue-message{text-align:left;color:var(--c-danger)}.vue-message.success{color:var(--c-success)}.vue-message p{margin:5px 0;color:var(--c-text-secondary);font-size:14px}.vue-success-actions{display:flex;gap:8px;margin-top:12px}.vue-actions{display:flex;gap:6px}.vue-reg-cards{display:none}.vue-reg-cards p{color:var(--c-sub);font-size:.85rem;margin:4px 0}.vue-book{max-width:480px;max-height:80vh;overflow:auto}.vue-options{display:flex;flex-direction:column;gap:8px}.vue-options button{text-align:left;padding:12px;border:1px solid var(--c-border);border-radius:var(--radius);background:var(--c-bg)}.vue-options button.selected{border-color:var(--color-brand-700);background:var(--color-mint-100)}.vue-options strong,.vue-options span{display:block}.vue-options span{font-size:.8rem;color:var(--c-sub)}
.step-flow{display:flex;gap:8px;margin-bottom:20px}.step-flow span{flex:1;padding:8px 6px;border-bottom:2px solid var(--c-border);color:var(--c-sub);font-size:12px;text-align:center}.step-flow .is-complete,.step-flow .is-active{border-color:var(--color-brand-700);color:var(--color-brand-700);font-weight:700}.booking-review{display:grid;gap:12px;margin:20px 0}.booking-review>div{display:flex;justify-content:space-between;gap:16px;padding-bottom:10px;border-bottom:1px solid var(--c-border)}.booking-review dt{color:var(--c-sub)}.booking-review dd{margin:0;font-weight:600;text-align:right}
@media(max-width:800px){.vue-reg-table{display:none}.vue-reg-cards{display:flex;flex-direction:column;gap:12px}}
</style>
