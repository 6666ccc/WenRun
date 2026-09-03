<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth } from '../stores'
import { cancelRegistration, getPatient, listRegistrations, updatePatient } from '../api'
import { updateProfile } from '../api/modules/user'
import { GENDER_MAP, REG_STATUS_MAP, formatDate, formatVisitSchedule } from '../utils'
import AppShell from '../components/AppShell.vue'
import PageHeader from '../components/PageHeader.vue'
import StatusBadge from '../components/StatusBadge.vue'
import UiState from '../components/UiState.vue'

const router = useRouter()
const { user, updateUser, logout } = useAuth()
const patient = ref(null), registrations = ref([]), loading = ref(true), error = ref(''), recordsError = ref(''), editing = ref(false), saving = ref(false), message = ref('')
const form = reactive({ name: '', gender: '', phone: '', idCard: '', birthDate: '', address: '', allergyHistory: '' })
function fill(data) { Object.assign(form, { name: data.name || '', gender: data.gender ?? '', phone: data.phone || '', idCard: data.idCard || '', birthDate: data.birthDate || '', address: data.address || '', allergyHistory: data.allergyHistory || '' }) }
async function load() {
  if (!user.value?.patientId) return void (loading.value = false)
  try {
    const [profile, records] = await Promise.allSettled([getPatient(user.value.patientId), listRegistrations({ userId: user.value.userId })])
    if (profile.status === 'fulfilled') { patient.value = profile.value; fill(patient.value) }
    else error.value = profile.reason?.message || '档案加载失败'
    if (records.status === 'fulfilled') registrations.value = records.value || []
    else recordsError.value = records.reason?.message || '挂号记录加载失败'
  }
  finally { loading.value = false }
}
onMounted(load)
async function save() {
  saving.value = true; message.value = ''
  try {
    await updatePatient(user.value.patientId, form)
    try { await updateProfile({ ...form }) } catch { /* 患者档案已保存 */ }
    patient.value = await getPatient(user.value.patientId)
    if (form.name && form.name !== user.value.realName) updateUser({ realName: form.name })
    editing.value = false; message.value = '保存成功'
  } catch (nextError) { message.value = nextError.message || '保存失败' }
  finally { saving.value = false }
}
async function signOut() { await logout(); router.replace('/login') }
const maskedIdCard = computed(() => {
  const value = patient.value?.idCard || ''
  if (!value) return '—'
  if (value.length <= 8) return `${value.slice(0, 2)}••••${value.slice(-2)}`
  return `${value.slice(0, 4)} •••••• ${value.slice(-4)}`
})
const pendingRegistrations = computed(() => registrations.value.filter((item) => item.status === 1))
const historyRegistrations = computed(() => registrations.value.filter((item) => item.status !== 1))
async function cancel(item) {
  try { await cancelRegistration(item.id); await load(); message.value = '挂号已取消' }
  catch (nextError) { message.value = nextError.message || '取消挂号失败' }
}
const fields = [
  { label: '姓名', key: 'name', autocomplete: 'name' },
  { label: '手机号', key: 'phone', type: 'tel', autocomplete: 'tel', inputmode: 'tel' },
  { label: '身份证号', key: 'idCard', autocomplete: 'off', inputmode: 'numeric' },
  { label: '出生日期', key: 'birthDate', type: 'date', autocomplete: 'bday' },
  { label: '地址', key: 'address', autocomplete: 'street-address' },
  { label: '过敏史', key: 'allergyHistory' },
]
</script>

<template>
  <AppShell>
    <PageHeader title="个人中心" subtitle="管理您的档案、预约与挂号记录" />
    <div v-if="message" class="card mb-md vue-message" :class="{success:message.includes('成功') || message.includes('已取消')}" :role="message.includes('成功') || message.includes('已取消') ? 'status' : 'alert'">{{ message }}</div>
    <UiState :loading="loading" :error="error" :empty="!patient" empty-text="暂无患者档案">
      <div class="vue-profile stagger">
        <aside class="card vue-profile-card">
          <div class="view-avatar-ring"><div class="view-avatar-ring__inner">{{ (patient.name || user?.username || '?')[0] }}</div></div>
          <h2>{{ patient.name || user?.username || '未设置姓名' }}</h2><p>{{ patient.patientNo }}</p>
          <button class="btn btn--danger btn--sm" type="button" @click="signOut">退出登录</button>
        </aside>
        <section class="clinic-panel vue-profile-main">
          <div class="clinic-panel__head"><h3>档案信息</h3><button class="btn btn--outline btn--sm clinic-panel__edit" @click="editing=!editing">{{ editing ? '取消编辑' : '编辑资料' }}</button></div>
          <div class="clinic-panel__body">
          <form v-if="editing" class="vue-form" @submit.prevent="save">
            <div v-for="field in fields" :key="field.key" class="form-group"><label class="form-label" :for="`profile-${field.key}`">{{ field.label }}</label><input :id="`profile-${field.key}`" v-model="form[field.key]" class="input" :type="field.type || 'text'" :autocomplete="field.autocomplete" :inputmode="field.inputmode" :placeholder="field.key==='allergyHistory'?'例如：青霉素过敏':''"></div>
            <div class="form-group"><label class="form-label" for="profile-gender">性别</label><select id="profile-gender" v-model="form.gender" class="input"><option value="">请选择</option><option :value="0">女</option><option :value="1">男</option></select></div>
            <button class="btn btn--primary" type="submit" :disabled="saving">{{ saving ? '保存中…' : '保存修改' }}</button>
          </form>
          <div v-else class="vue-info">
            <div><small>姓名</small><b>{{ patient.name || '—' }}</b></div><div><small>性别</small><b>{{ GENDER_MAP[patient.gender] || '未知' }}</b></div>
            <div><small>手机号</small><b>{{ patient.phone || '—' }}</b></div><div><small>身份证号</small><b>{{ maskedIdCard }}</b></div>
            <div><small>出生日期</small><b>{{ formatDate(patient.birthDate) }}</b></div><div><small>地址</small><b>{{ patient.address || '—' }}</b></div>
            <div class="wide"><small>过敏史</small><b>{{ patient.allergyHistory || '无' }}</b></div>
          </div>
          </div>
        </section>
      </div>
      <section class="clinic-panel vue-my-registrations" aria-labelledby="my-registrations-title">
        <div class="clinic-panel__head"><div><h3 id="my-registrations-title">我的挂号</h3><p>待就诊与历史挂号统一在此管理</p></div><span class="vue-record-count">{{ pendingRegistrations.length }} 项待就诊</span></div>
        <div class="clinic-panel__body">
          <p v-if="recordsError" class="vue-record-error" role="alert">{{ recordsError }}</p>
          <div v-else-if="registrations.length" class="vue-registration-list">
            <article v-for="item in registrations" :key="item.id" class="vue-registration-row">
              <div><strong>{{ item.deptName }} · {{ item.staffName }}</strong><span>{{ formatVisitSchedule(item.workDate, item.timePeriod) }}</span><small>挂号单 {{ item.regNo }}</small></div>
              <StatusBadge :status="item.status" :map="REG_STATUS_MAP" />
              <div class="vue-registration-actions"><RouterLink class="btn btn--outline btn--sm" :to="`/registration/${item.id}`">详情</RouterLink><button v-if="item.status===1" class="btn btn--danger btn--sm" type="button" @click="cancel(item)">取消</button></div>
            </article>
          </div>
          <div v-else class="vue-record-empty"><strong>还没有挂号记录</strong><p>预约成功后，记录会显示在这里。</p><RouterLink class="btn btn--primary btn--sm" to="/registration">去预约挂号</RouterLink></div>
          <p v-if="historyRegistrations.length" class="vue-record-hint">含 {{ historyRegistrations.length }} 条历史记录</p>
        </div>
      </section>
    </UiState>
  </AppShell>
</template>

<style scoped>
.vue-message{text-align:center;color:var(--c-danger)}.vue-message.success{color:var(--c-success)}.vue-profile{display:flex;gap:24px}.vue-profile-card{width:240px;text-align:center;padding:32px 24px;flex-shrink:0}.vue-profile-card h2{font-family:var(--font-serif);margin:12px 0 4px}.vue-profile-card p{color:var(--c-muted)}.vue-profile-main{flex:1}.clinic-panel__edit{border-color:rgba(255,255,255,.45);background:transparent;color:#fff}.clinic-panel__edit:hover:not(:disabled){background:rgba(255,255,255,.12);border-color:#fff;color:#fff}.vue-info,.vue-form{display:grid;grid-template-columns:1fr 1fr;gap:14px 28px}.vue-info small,.vue-info b{display:block}.vue-info small{color:var(--c-muted)}.vue-info .wide{grid-column:1/-1}
.vue-my-registrations{margin-top:24px}.vue-my-registrations .clinic-panel__head{align-items:center}.vue-my-registrations .clinic-panel__head p{margin:4px 0 0;color:var(--color-text-secondary);font-size:13px;font-weight:400}.vue-record-count{color:var(--color-brand-700);font-size:13px;font-weight:750}.vue-registration-list{display:grid}.vue-registration-row{display:grid;grid-template-columns:minmax(0,1fr) auto auto;align-items:center;gap:16px;padding:15px 0;border-bottom:1px solid var(--color-border)}.vue-registration-row:first-child{padding-top:0}.vue-registration-row:last-child{border-bottom:0;padding-bottom:0}.vue-registration-row strong,.vue-registration-row span,.vue-registration-row small{display:block}.vue-registration-row span{margin-top:4px;color:var(--color-text-secondary);font-size:14px}.vue-registration-row small{margin-top:4px;color:var(--color-text-muted);font-size:12px}.vue-registration-actions{display:flex;gap:8px}.vue-record-empty{display:grid;justify-items:start;gap:8px;padding:8px 0}.vue-record-empty p{margin:0;color:var(--color-text-secondary);font-size:14px}.vue-record-hint{margin:14px 0 0;color:var(--color-text-secondary);font-size:13px}.vue-record-error{margin:0;color:var(--color-danger)}
@media(max-width:700px){.vue-profile{flex-direction:column}.vue-profile-card{width:auto}.vue-info,.vue-form{grid-template-columns:1fr 1fr}.vue-registration-row{grid-template-columns:1fr auto;align-items:start}.vue-registration-row>.shared-status{grid-column:2;grid-row:1}.vue-registration-actions{grid-column:1/-1}}
</style>
