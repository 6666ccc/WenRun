<script setup>
import { computed, ref, watch } from 'vue'
import { useAuth } from '../../stores'
import { cancelRegistration, listRegistrations, listSchedules, rescheduleRegistration } from '../../api'
import { REG_STATUS_MAP, formatDateTime, formatTimePeriod, formatVisitSchedule } from '../../utils'
import { isBookableSchedule, isOccupiedSlot } from '../../utils/scheduleDate'
import ConfirmDialog from '../ConfirmDialog.vue'
import StatusBadge from '../StatusBadge.vue'
import UiState from '../UiState.vue'

const props = defineProps({
  id: { type: [String, Number], required: true },
  /** 抽屉头部已有返回按钮时可关闭组件内的返回按钮。 */
  showBack: { type: Boolean, default: true },
})
const emit = defineEmits(['cancelled', 'back'])

const { user } = useAuth()
const registration = ref(null)
const registrations = ref([]), schedules = ref([])
const loading = ref(true), error = ref(''), operationError = ref('')
const cancelOpen = ref(false), cancelling = ref(false)
const rescheduleOpen = ref(false), rescheduling = ref(false), targetScheduleId = ref('')
const availableSchedules = computed(() => schedules.value.filter((item) => (
  String(item.id) !== String(registration.value?.scheduleId)
  && Number(item.remainingCount) > 0
  && isBookableSchedule(item.workDate, item.timePeriod)
  && !isOccupiedSlot(item, registrations.value.filter((entry) => entry.id !== registration.value?.id))
)))

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [recordList, slotList] = await Promise.all([
      listRegistrations({ userId: user.value.userId }),
      listSchedules(),
    ])
    registrations.value = recordList || []
    schedules.value = slotList || []
    registration.value = registrations.value.find((item) => String(item.id) === String(props.id))
    if (!registration.value) throw new Error('挂号记录不存在')
  } catch (nextError) { error.value = nextError.message || '加载失败' }
  finally { loading.value = false }
}
watch(() => props.id, load, { immediate: true })

async function cancel() {
  cancelling.value = true
  try {
    await cancelRegistration(Number(props.id))
    cancelOpen.value = false
    emit('cancelled')
  }
  catch (nextError) { error.value = nextError.message || '取消失败'; cancelOpen.value = false }
  finally { cancelling.value = false }
}
async function reschedule() {
  if (!targetScheduleId.value) return
  rescheduling.value = true
  operationError.value = ''
  try {
    await rescheduleRegistration(Number(props.id), Number(targetScheduleId.value))
    rescheduleOpen.value = false
    targetScheduleId.value = ''
    await load()
  } catch (nextError) { operationError.value = nextError.message || '改约失败，请稍后重试' }
  finally { rescheduling.value = false }
}
</script>

<template>
  <div class="record">
    <button v-if="showBack" class="view-back" type="button" @click="emit('back')">‹ 返回个人中心</button>
    <p v-if="operationError" class="vue-operation-error" role="alert">{{ operationError }}</p>
    <UiState :loading="loading" :error="error" :empty="!registration" empty-text="挂号记录不存在">
      <div class="vue-record">
        <section class="clinic-panel"><div class="clinic-panel__head"><h2>挂号详情</h2><StatusBadge :status="registration.status" :map="REG_STATUS_MAP" /></div>
          <div class="clinic-panel__body">
          <div class="vue-info"><div><small>挂号编号</small><b>{{ registration.regNo }}</b></div><div><small>患者</small><b>{{ registration.patientName }}</b></div><div><small>专业方向</small><b>{{ registration.deptName }}</b></div><div><small>专家</small><b>{{ registration.staffName }}</b></div><div><small>预约时间</small><b>{{ formatVisitSchedule(registration.workDate,registration.timePeriod) }}</b></div><div><small>提交时间</small><b>{{ formatDateTime(registration.regTime) }}</b></div></div>
          <div v-if="registration.status===1" class="vue-actions mt-md"><button class="btn btn--primary btn--sm" type="button" @click="rescheduleOpen=true">修改号源</button><button class="btn btn--danger btn--sm" type="button" @click="cancelOpen=true">取消挂号</button></div>
          </div>
        </section>
      </div>
    </UiState>
    <Teleport to="body">
      <ConfirmDialog :show="cancelOpen" title="取消挂号" :message="`确认取消 ${registration?.regNo}？号源将立即释放。`" :loading="cancelling" @confirm="cancel" @cancel="cancelOpen=false" />
      <div v-if="rescheduleOpen" class="shared-dialog-overlay" role="presentation" @click="rescheduleOpen=false"><section class="shared-dialog vue-reschedule" role="dialog" aria-modal="true" aria-labelledby="reschedule-title" @click.stop>
        <h3 id="reschedule-title">修改号源</h3><p>选择新的专家与时段。改约成功后，原号源会自动释放。</p>
        <label><span>目标号源</span><select v-model="targetScheduleId" class="input"><option value="">请选择</option><option v-for="slot in availableSchedules" :key="slot.id" :value="slot.id">{{ slot.deptName }} · {{ slot.staffName }} · {{ slot.workDate }} {{ formatTimePeriod(slot.timePeriod) }} · 余 {{ slot.remainingCount }}</option></select></label>
        <p v-if="!availableSchedules.length" class="vue-reschedule__empty">当前没有其他可改约号源。</p>
        <div class="shared-dialog__actions"><button class="btn btn--ghost" type="button" @click="rescheduleOpen=false">返回</button><button class="btn btn--primary" type="button" :disabled="!targetScheduleId || rescheduling" @click="reschedule">{{ rescheduling ? '改约中…' : '确认改约' }}</button></div>
      </section></div>
    </Teleport>
  </div>
</template>

<style scoped>
.vue-record{display:flex;flex-direction:column;gap:16px}.vue-record h2{margin:0}.vue-info{display:grid;grid-template-columns:1fr 1fr;gap:12px 24px}.vue-info small,.vue-info b{display:block}.vue-info small{color:var(--c-muted)}.vue-actions{display:flex;gap:10px}.vue-operation-error{padding:10px 14px;border-radius:10px;background:var(--color-danger-bg);color:var(--color-danger)}.vue-reschedule{max-width:620px}.vue-reschedule h3{margin-top:0}.vue-reschedule>p{color:var(--color-text-secondary)}.vue-reschedule label{display:grid;gap:7px;margin:20px 0}.vue-reschedule label span{font-weight:700}.vue-reschedule__empty{padding:12px;border-radius:10px;background:var(--color-bg)}
</style>
