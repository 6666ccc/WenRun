<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuth } from '../stores'
import { cancelRegistration, listExamRequests, listPrescriptions, listRegistrations, listVisits } from '../api'
import { EXAM_STATUS_MAP, REG_STATUS_MAP, RX_STATUS_MAP, VISIT_STATUS_MAP, formatDateTime, formatMoney, formatVisitSchedule } from '../utils'
import AppShell from '../components/AppShell.vue'
import ConfirmDialog from '../components/ConfirmDialog.vue'
import StatusBadge from '../components/StatusBadge.vue'
import UiState from '../components/UiState.vue'

const route = useRoute(), router = useRouter()
const { user } = useAuth()
const registration = ref(null), visits = ref([]), prescriptions = ref([]), exams = ref([])
const loading = ref(true), error = ref(''), cancelOpen = ref(false), cancelling = ref(false)
onMounted(async () => {
  try {
    const list = await listRegistrations({ userId: user.value.userId })
    registration.value = (list || []).find((item) => String(item.id) === String(route.params.id))
    if (!registration.value) throw new Error('挂号记录不存在')
    const allVisits = await listVisits({})
    visits.value = (allVisits || []).filter((item) => item.registrationId === registration.value.id)
    const related = await Promise.all(visits.value.flatMap((visit) => [
      listPrescriptions({ visitId: visit.id }).then((items) => prescriptions.value.push(...(items || []))).catch(() => {}),
      listExamRequests({ visitId: visit.id }).then((items) => exams.value.push(...(items || []))).catch(() => {}),
    ]))
    void related
  } catch (nextError) { error.value = nextError.message || '加载失败' }
  finally { loading.value = false }
})
async function cancel() {
  cancelling.value = true
  try { await cancelRegistration(Number(route.params.id)); router.replace('/user') }
  catch (nextError) { error.value = nextError.message || '取消失败'; cancelOpen.value = false }
  finally { cancelling.value = false }
}
</script>

<template>
  <AppShell>
    <button class="view-back" @click="router.push('/user')">‹ 返回个人中心</button>
    <UiState :loading="loading" :error="error" :empty="!registration" empty-text="挂号记录不存在">
      <div class="vue-record">
        <section class="clinic-panel"><div class="clinic-panel__head"><h2>挂号详情</h2><StatusBadge :status="registration.status" :map="REG_STATUS_MAP" /></div>
          <div class="clinic-panel__body">
          <div class="vue-info"><div><small>挂号编号</small><b>{{ registration.regNo }}</b></div><div><small>患者</small><b>{{ registration.patientName }}</b></div><div><small>科室</small><b>{{ registration.deptName }}</b></div><div><small>医生</small><b>{{ registration.staffName }}</b></div><div><small>就诊时间</small><b>{{ formatVisitSchedule(registration.workDate,registration.timePeriod) }}</b></div><div><small>挂号时间</small><b>{{ formatDateTime(registration.regTime) }}</b></div><div><small>挂号费</small><b>{{ formatMoney(registration.regFee) }}</b></div></div>
          <button v-if="registration.status===1" class="btn btn--danger btn--sm mt-md" @click="cancelOpen=true">退号</button>
          </div>
        </section>
        <section v-for="visit in visits" :key="visit.id" class="clinic-panel"><div class="clinic-panel__head"><h3>就诊记录</h3><StatusBadge :status="visit.status" :map="VISIT_STATUS_MAP" /></div>
          <div class="clinic-panel__body">
          <div class="vue-info"><div><small>就诊编号</small><b>{{ visit.visitNo }}</b></div><div><small>就诊时间</small><b>{{ formatDateTime(visit.visitTime) }}</b></div><div><small>主诉</small><b>{{ visit.chiefComplaint || '—' }}</b></div><div><small>诊断</small><b>{{ visit.diagnosis || '—' }}</b></div></div>
          <div v-for="rx in prescriptions.filter(item=>item.visitId===visit.id)" :key="rx.id" class="vue-related"><div class="flex-between"><strong>处方 {{ rx.rxNo }}</strong><StatusBadge :status="rx.status" :map="RX_STATUS_MAP" /></div><p>总金额：{{ formatMoney(rx.totalAmount) }}</p></div>
          <div v-for="exam in exams.filter(item=>item.visitId===visit.id)" :key="exam.id" class="vue-related"><div class="flex-between"><strong>检查申请 {{ exam.requestNo }}</strong><StatusBadge :status="exam.status" :map="EXAM_STATUS_MAP" /></div><p>费用：{{ formatMoney(exam.amount) }}</p></div>
          </div>
        </section>
      </div>
    </UiState>
    <ConfirmDialog :show="cancelOpen" title="退号确认" :message="`确认退号 ${registration?.regNo}？号源将归还排班。`" :loading="cancelling" @confirm="cancel" @cancel="cancelOpen=false" />
  </AppShell>
</template>

<style scoped>
.vue-record{display:flex;flex-direction:column;gap:16px}.vue-record h2,.vue-record h3{margin:0}.vue-info{display:grid;grid-template-columns:1fr 1fr;gap:12px 24px}.vue-info small,.vue-info b{display:block}.vue-info small{color:var(--c-muted)}.vue-related{margin-top:14px;padding:16px;background:var(--c-bg);border-radius:var(--radius)}
</style>
