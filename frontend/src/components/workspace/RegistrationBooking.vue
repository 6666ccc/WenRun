<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { createRegistration, listRegistrations, listSchedules } from '../../api'
import { useAuth } from '../../stores'
import { formatMoney, formatTimePeriod } from '../../utils'
import { isBookableSchedule, isOccupiedSlot, shiftClinicDate, todayISO } from '../../utils/scheduleDate'
import UiIcon from '../UiIcon.vue'
import UiState from '../UiState.vue'

const { activePatientId } = useAuth()
const schedules = ref([])
const myRegistrations = ref([])
const loading = ref(true)
const error = ref('')
const booking = ref(false)
const selected = ref(null)
const reviewing = ref(false)
const message = ref('')
const filters = reactive({ date: '', dept: '', doctor: '' })
const PAGE_SIZE = 20
const visibleLimit = ref(PAGE_SIZE)

const departments = computed(() => [...new Set(schedules.value.map((item) => item.deptName).filter(Boolean))])
const doctors = computed(() => [...new Set(
  schedules.value.filter((item) => !filters.dept || item.deptName === filters.dept).map((item) => item.staffName).filter(Boolean),
)])
const bookableSchedules = computed(() => schedules.value.filter((item) => {
  if (Number(item.remainingCount) <= 0) return false
  if (!isBookableSchedule(item.workDate, item.timePeriod)) return false
  if (isOccupiedSlot(item, myRegistrations.value)) return false
  return true
}))
const availableSchedules = computed(() => bookableSchedules.value.filter((item) => {
  if (filters.date && item.workDate !== filters.date) return false
  if (filters.dept && item.deptName !== filters.dept) return false
  if (filters.doctor && item.staffName !== filters.doctor) return false
  return true
}))
const visibleSchedules = computed(() => availableSchedules.value.slice(0, visibleLimit.value))
const hasMore = computed(() => visibleSchedules.value.length < availableSchedules.value.length)
const resultSummary = computed(() => availableSchedules.value.length
  ? `共 ${availableSchedules.value.length} 个可预约排班，当前显示 ${visibleSchedules.value.length} 个`
  : '没有符合条件的可预约排班')
watch(() => filters.dept, () => {
  if (filters.doctor && !doctors.value.includes(filters.doctor)) filters.doctor = ''
})
watch([() => filters.date, () => filters.dept, () => filters.doctor], () => {
  visibleLimit.value = PAGE_SIZE
})

async function load() {
  loading.value = true
  error.value = ''
  try {
    schedules.value = (await listSchedules()) || []
    if (activePatientId.value) {
      try { myRegistrations.value = (await listRegistrations({ patientId: activePatientId.value })) || [] }
      catch { myRegistrations.value = [] }
    } else {
      myRegistrations.value = []
    }
    if (!filters.date) {
      const dates = [...new Set(bookableSchedules.value.map((item) => item.workDate).filter(Boolean))].sort()
      filters.date = dates.includes(todayISO()) ? todayISO() : (dates[0] || '')
    }
  }
  catch (nextError) { error.value = nextError.message || '号源加载失败，请稍后重试' }
  finally { loading.value = false }
}
onMounted(load)
watch(activePatientId, load)

function clearFilters() { Object.assign(filters, { date: '', dept: '', doctor: '' }) }
function setDate(offset) {
  filters.date = shiftClinicDate(offset)
}
function scheduleActionLabel(schedule) {
  return `选择 ${schedule.workDate} ${formatTimePeriod(schedule.timePeriod)} ${schedule.deptName} ${schedule.staffName}号源`
}
function selectSchedule(schedule) { selected.value = schedule; reviewing.value = true }
async function book() {
  if (!selected.value || !activePatientId.value) return
  booking.value = true
  try {
    await createRegistration({ patientId: activePatientId.value, scheduleId: selected.value.id })
    schedules.value = schedules.value.map((item) => item.id === selected.value.id ? { ...item, remainingCount: Math.max(0, Number(item.remainingCount) - 1) } : item)
    myRegistrations.value = [...myRegistrations.value, {
      status: 1,
      staffId: selected.value.staffId,
      workDate: selected.value.workDate,
      timePeriod: selected.value.timePeriod,
    }]
    message.value = `已为您预约 ${selected.value.deptName} · ${selected.value.staffName}`
    selected.value = null
    reviewing.value = false
  } catch (nextError) { message.value = nextError.message || '挂号失败，请稍后重试' }
  finally { booking.value = false }
}
</script>

<template>
  <div class="booking">
    <section v-if="message" class="card mb-md vue-message" :class="{ success: message.startsWith('已为您预约') }" :role="message.startsWith('已为您预约') ? 'status' : 'alert'">{{ message }}</section>
    <UiState :loading="loading" :error="error">
      <section class="clinic-panel vue-booking-panel" aria-labelledby="booking-filters-title">
        <div class="clinic-panel__head"><h2 id="booking-filters-title">查找可预约号源</h2><span aria-live="polite">{{ resultSummary }}</span></div>
        <div class="clinic-panel__body">
          <div class="vue-filter-bar">
            <label><span>就诊日期</span><input v-model="filters.date" class="input" type="date" :min="todayISO()" /></label>
            <label><span>科室</span><select v-model="filters.dept" class="input"><option value="">全部科室</option><option v-for="dept in departments" :key="dept" :value="dept">{{ dept }}</option></select></label>
            <label><span>医生</span><select v-model="filters.doctor" class="input"><option value="">全部医生</option><option v-for="doctor in doctors" :key="doctor" :value="doctor">{{ doctor }}</option></select></label>
            <button class="btn btn--ghost vue-filter-reset" type="button" @click="clearFilters">清空筛选</button>
          </div>
          <div class="vue-date-presets" aria-label="快捷选择就诊日期"><button class="btn btn--outline btn--sm" type="button" :aria-pressed="filters.date === todayISO()" @click="setDate(0)">今天</button><button class="btn btn--outline btn--sm" type="button" :aria-pressed="filters.date === shiftClinicDate(1)" @click="setDate(1)">明天</button><button class="btn btn--outline btn--sm" type="button" :aria-pressed="!filters.date" @click="filters.date=''">所有日期</button></div>
        </div>
      </section>
      <section class="vue-schedule-results" aria-live="polite" aria-label="可预约号源列表">
        <article v-for="(schedule, index) in visibleSchedules" :key="schedule.id" class="vue-schedule-card" :style="{ '--schedule-index': Math.min(index, 8) }">
          <div class="vue-schedule-card__main"><span class="vue-schedule-card__dept">{{ schedule.deptName }}</span><h2 :id="`schedule-${schedule.id}`">{{ schedule.staffName }}</h2><p>{{ schedule.workDate }} · {{ formatTimePeriod(schedule.timePeriod) }}</p></div>
          <div class="vue-schedule-card__meta"><strong>余号 {{ schedule.remainingCount }}</strong><span>{{ formatMoney(schedule.registerFee) }}</span></div>
          <button class="btn btn--primary" type="button" :aria-label="scheduleActionLabel(schedule)" @click="selectSchedule(schedule)">选择号源</button>
        </article>
        <div v-if="!availableSchedules.length" class="vue-no-schedules"><UiIcon name="search" :size="28" /><strong>没有符合条件的号源</strong><p>可尝试切换日期、科室或医生。</p><button class="btn btn--outline btn--sm" type="button" @click="clearFilters">清空筛选</button></div>
        <div v-else-if="hasMore" class="vue-load-more">
          <p>已显示 {{ visibleSchedules.length }} / {{ availableSchedules.length }} 个号源</p>
          <button class="btn btn--outline" type="button" @click="visibleLimit += PAGE_SIZE">再显示 {{ Math.min(PAGE_SIZE, availableSchedules.length - visibleSchedules.length) }} 个</button>
        </div>
      </section>
    </UiState>
    <Teleport to="body">
      <div v-if="reviewing && selected" class="shared-dialog-overlay" role="presentation" @click="reviewing=false"><div class="shared-dialog vue-review-dialog" role="dialog" aria-modal="true" aria-labelledby="booking-title" @click.stop>
        <p class="vue-review-dialog__eyebrow">确认预约</p><h3 id="booking-title">核对挂号信息</h3><p>提交后将创建挂号记录，可在个人档案查看和管理。</p>
        <dl class="booking-review"><div><dt>科室 / 医生</dt><dd>{{ selected.deptName }} · {{ selected.staffName }}</dd></div><div><dt>日期 / 时段</dt><dd>{{ selected.workDate }} · {{ formatTimePeriod(selected.timePeriod) }}</dd></div><div><dt>挂号费</dt><dd>{{ formatMoney(selected.registerFee) }}</dd></div><div><dt>剩余号源</dt><dd>{{ selected.remainingCount }}</dd></div></dl>
        <div class="shared-dialog__actions"><button class="btn btn--ghost" type="button" @click="reviewing=false">返回筛选</button><button class="btn btn--primary" type="button" :disabled="booking" @click="book">{{ booking ? '提交中…' : '确认挂号' }}</button></div>
      </div></div>
    </Teleport>
  </div>
</template>

<style scoped>
.vue-message{color:var(--color-danger);text-align:left}.vue-message.success{color:var(--color-success)}
.vue-booking-panel{margin-bottom:20px}.vue-booking-panel .clinic-panel__head span{color:var(--color-text-secondary);font-size:13px;font-weight:600}
.vue-filter-bar{display:grid;grid-template-columns:repeat(3,minmax(0,1fr)) auto;align-items:end;gap:14px}.vue-filter-bar label{display:grid;gap:7px;color:var(--color-text-secondary);font-size:13px;font-weight:700}.vue-filter-reset{min-height:44px;white-space:nowrap}.vue-date-presets{display:flex;gap:8px;margin-top:14px}
.vue-schedule-results{display:grid;gap:12px}.vue-schedule-card{position:relative;overflow:hidden;display:grid;grid-template-columns:minmax(0,1fr) auto auto;align-items:center;gap:24px;padding:20px 22px;border:1px solid var(--color-border);border-radius:15px;background:linear-gradient(110deg,var(--color-surface),#fbfefd);box-shadow:var(--shadow-xs);animation:schedule-card-in var(--motion-reveal) calc(var(--schedule-index) * 35ms) var(--ease-clinical) both;transition:border-color var(--motion-fast) ease,box-shadow var(--motion-fast) ease,transform var(--motion-fast) var(--ease-clinical)}.vue-schedule-card::before{content:"";position:absolute;left:0;top:16px;bottom:16px;width:3px;border-radius:0 3px 3px 0;background:var(--color-mint-300);opacity:.45;transition:opacity var(--motion-fast) ease,transform var(--motion-fast) var(--ease-clinical)}.vue-schedule-card:hover,.vue-schedule-card:focus-within{border-color:var(--color-border-strong);box-shadow:var(--shadow-clinical);transform:translateY(-1px)}.vue-schedule-card:hover::before,.vue-schedule-card:focus-within::before{opacity:1;transform:scaleY(1.2)}.vue-schedule-card__dept{color:var(--color-brand-700);font-size:13px;font-weight:750}.vue-schedule-card h2{margin:5px 0;font-size:19px}.vue-schedule-card p{margin:0;color:var(--color-text-secondary);font-size:14px}.vue-schedule-card__meta{display:grid;gap:5px;min-width:96px;text-align:right}.vue-schedule-card__meta strong{color:var(--color-brand-700);font-size:14px}.vue-schedule-card__meta span{color:var(--color-text-secondary);font-size:14px}.vue-no-schedules{display:grid;justify-items:center;gap:7px;padding:52px 20px;border:1px dashed var(--color-border-strong);border-radius:15px;color:var(--color-text-secondary);text-align:center}.vue-no-schedules strong{color:var(--color-text);font-size:17px}.vue-no-schedules p{margin:0;font-size:14px}
.vue-load-more{display:grid;justify-items:center;gap:10px;padding:18px;color:var(--color-text-secondary);font-size:13px}.vue-load-more p{margin:0}.vue-date-presets button[aria-pressed="true"]{border-color:var(--color-brand-700);background:var(--color-mint-050);color:var(--color-brand-800)}
.vue-review-dialog{max-width:480px}.vue-review-dialog__eyebrow{margin:0 0 6px!important;color:var(--color-brand-700)!important;font-size:12px!important;font-weight:750;letter-spacing:.08em}.booking-review{display:grid;gap:12px;margin:20px 0}.booking-review>div{display:flex;justify-content:space-between;gap:16px;padding-bottom:10px;border-bottom:1px solid var(--color-border)}.booking-review dt{color:var(--color-text-secondary)}.booking-review dd{margin:0;font-weight:700;text-align:right}
@keyframes schedule-card-in{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}
@media(max-width:700px){.vue-filter-bar{grid-template-columns:1fr}.vue-filter-reset{width:100%}.vue-schedule-card{grid-template-columns:1fr auto;gap:14px;padding:18px}.vue-schedule-card__meta{grid-column:1;text-align:left}.vue-schedule-card>.btn{grid-column:2;grid-row:1 / span 2;align-self:center}.vue-date-presets{flex-wrap:wrap}}
@media(prefers-reduced-motion:reduce){.vue-schedule-card{animation:none;transition:none;transform:none}.vue-schedule-card::before{transition:none}}
</style>
