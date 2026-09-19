<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth } from '../../stores'
import {
  cancelRegistration,
  createHealthProfile,
  deleteHealthProfile,
  deleteHealthSnapshot,
  getHealthProfile,
  getPatient,
  listHealthSnapshots,
  listRegistrations,
  updateHealthProfile,
  updatePatient,
} from '../../api'
import { updateProfile } from '../../api/modules/user'
import { GENDER_MAP, REG_STATUS_MAP, formatDate, formatDateTime, formatVisitSchedule } from '../../utils'
import {
  calcBmi,
  emptyHealthForm,
  fillHealthForm,
  formatBloodPressure,
  formatGlucoseType,
  toHealthPayload,
} from '../../utils/healthProfile'
import StatusBadge from '../StatusBadge.vue'
import UiState from '../UiState.vue'

const router = useRouter()
const { user, updateUser, logout } = useAuth()
const patient = ref(null)
const registrations = ref([])
const health = ref(null)
const snapshots = ref([])
const loading = ref(true)
const error = ref('')
const recordsError = ref('')
const healthError = ref('')
const editing = ref(false)
const healthEditing = ref(false)
const saving = ref(false)
const healthSaving = ref(false)
const message = ref('')
const form = reactive({ name: '', gender: '', phone: '', idCard: '', birthDate: '', address: '', allergyHistory: '' })
const healthForm = reactive(emptyHealthForm())

function fill(data) {
  Object.assign(form, {
    name: data.name || '',
    gender: data.gender ?? '',
    phone: data.phone || '',
    idCard: data.idCard || '',
    birthDate: data.birthDate || '',
    address: data.address || '',
    allergyHistory: data.allergyHistory || '',
  })
}

function fillHealth(data) {
  Object.assign(healthForm, fillHealthForm(data || {}))
}

async function load() {
  if (!user.value?.patientId) return void (loading.value = false)
  try {
    const [profile, records, healthProfile, history] = await Promise.allSettled([
      getPatient(user.value.patientId),
      listRegistrations({ userId: user.value.userId }),
      getHealthProfile(user.value.patientId),
      listHealthSnapshots(user.value.patientId),
    ])
    if (profile.status === 'fulfilled') {
      patient.value = profile.value
      fill(patient.value)
    } else {
      error.value = profile.reason?.message || '档案加载失败'
    }
    if (records.status === 'fulfilled') registrations.value = records.value || []
    else recordsError.value = records.reason?.message || '挂号记录加载失败'
    if (healthProfile.status === 'fulfilled') {
      health.value = healthProfile.value
      fillHealth(health.value)
    } else {
      healthError.value = healthProfile.reason?.message || '健康档案加载失败'
    }
    if (history.status === 'fulfilled') snapshots.value = history.value || []
  } finally {
    loading.value = false
  }
}

onMounted(load)

async function save() {
  saving.value = true
  message.value = ''
  try {
    await updatePatient(user.value.patientId, form)
    try { await updateProfile({ ...form }) } catch { /* 患者档案已保存 */ }
    patient.value = await getPatient(user.value.patientId)
    if (form.name && form.name !== user.value.realName) updateUser({ realName: form.name })
    editing.value = false
    message.value = '保存成功'
  } catch (nextError) {
    message.value = nextError.message || '保存失败'
  } finally {
    saving.value = false
  }
}

async function saveHealth() {
  healthSaving.value = true
  message.value = ''
  try {
    const payload = toHealthPayload(healthForm)
    const saved = health.value?.exists
      ? await updateHealthProfile(user.value.patientId, payload)
      : await createHealthProfile(user.value.patientId, payload)
    health.value = saved
    fillHealth(saved)
    snapshots.value = await listHealthSnapshots(user.value.patientId)
    healthEditing.value = false
    message.value = '健康档案已保存'
  } catch (nextError) {
    message.value = nextError.message || '健康档案保存失败'
  } finally {
    healthSaving.value = false
  }
}

function cancelHealthEdit() {
  fillHealth(health.value)
  healthEditing.value = false
}

async function removeHealth() {
  if (!health.value?.exists) return
  if (!window.confirm('清空当前健康档案？历史快照仍会保留。')) return
  message.value = ''
  try {
    await deleteHealthProfile(user.value.patientId)
    health.value = { patientId: user.value.patientId, exists: false }
    fillHealth({})
    healthEditing.value = false
    message.value = '健康档案已清空'
  } catch (nextError) {
    message.value = nextError.message || '清空失败'
  }
}

async function removeSnapshot(item) {
  if (!window.confirm('删除这条历史快照？')) return
  message.value = ''
  try {
    await deleteHealthSnapshot(user.value.patientId, item.id)
    snapshots.value = snapshots.value.filter((row) => row.id !== item.id)
    message.value = '快照已删除'
  } catch (nextError) {
    message.value = nextError.message || '删除快照失败'
  }
}

async function signOut() {
  await logout()
  router.replace('/login')
}

const maskedIdCard = computed(() => {
  const value = patient.value?.idCard || ''
  if (!value) return '—'
  if (value.length <= 8) return `${value.slice(0, 2)}••••${value.slice(-2)}`
  return `${value.slice(0, 4)} •••••• ${value.slice(-4)}`
})
const pendingRegistrations = computed(() => registrations.value.filter((item) => item.status === 1))
const historyRegistrations = computed(() => registrations.value.filter((item) => item.status !== 1))
const healthBmi = computed(() => calcBmi(health.value?.heightCm, health.value?.weightKg))
const healthBloodPressure = computed(() => formatBloodPressure(health.value?.systolicMmhg, health.value?.diastolicMmhg))
const successMessage = computed(() => message.value.includes('成功') || message.value.includes('已取消') || message.value.includes('已保存') || message.value.includes('已清空') || message.value.includes('已删除'))

async function cancel(item) {
  try {
    await cancelRegistration(item.id)
    await load()
    message.value = '挂号已取消'
  } catch (nextError) {
    message.value = nextError.message || '取消挂号失败'
  }
}

const fields = [
  { label: '姓名', key: 'name', autocomplete: 'name' },
  { label: '手机号', key: 'phone', type: 'tel', autocomplete: 'tel', inputmode: 'tel' },
  { label: '身份证号', key: 'idCard', autocomplete: 'off', inputmode: 'numeric' },
  { label: '出生日期', key: 'birthDate', type: 'date', autocomplete: 'bday' },
  { label: '地址', key: 'address', autocomplete: 'street-address' },
  { label: '过敏史', key: 'allergyHistory' },
]

const healthFields = [
  { label: '身高 cm', key: 'heightCm', type: 'number', step: '0.1', min: '50', max: '250' },
  { label: '体重 kg', key: 'weightKg', type: 'number', step: '0.1', min: '10', max: '300' },
  { label: '收缩压 mmHg', key: 'systolicMmhg', type: 'number', min: '60', max: '250' },
  { label: '舒张压 mmHg', key: 'diastolicMmhg', type: 'number', min: '40', max: '180' },
  { label: '血糖 mmol/L', key: 'glucoseMmol', type: 'number', step: '0.1', min: '1', max: '40' },
  { label: '心率 次/分', key: 'heartRateBpm', type: 'number', min: '30', max: '220' },
]
</script>

<template>
  <div class="profile">
    <div v-if="message" class="card mb-md vue-message" :class="{success: successMessage}" :role="successMessage ? 'status' : 'alert'">{{ message }}</div>
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

      <section class="clinic-panel vue-health" aria-labelledby="health-profile-title">
        <div class="clinic-panel__head">
          <div>
            <h3 id="health-profile-title">健康档案</h3>
            <p>体征与病史单独保存，每次保存会留下一条历史快照</p>
          </div>
          <div class="vue-health-actions">
            <button v-if="health?.exists && !healthEditing" class="btn btn--outline btn--sm clinic-panel__edit" type="button" @click="removeHealth">清空</button>
            <button class="btn btn--outline btn--sm clinic-panel__edit" type="button" @click="healthEditing ? cancelHealthEdit() : healthEditing = true">{{ healthEditing ? '取消编辑' : (health?.exists ? '编辑档案' : '填写档案') }}</button>
          </div>
        </div>
        <div class="clinic-panel__body">
          <p v-if="healthError" class="vue-record-error" role="alert">{{ healthError }}</p>
          <form v-else-if="healthEditing" class="vue-form vue-health-form" @submit.prevent="saveHealth">
            <div v-for="field in healthFields" :key="field.key" class="form-group">
              <label class="form-label" :for="`health-${field.key}`">{{ field.label }}</label>
              <input :id="`health-${field.key}`" v-model="healthForm[field.key]" class="input" :type="field.type" :step="field.step" :min="field.min" :max="field.max" inputmode="decimal">
            </div>
            <div class="form-group">
              <label class="form-label" for="health-glucoseType">血糖类型</label>
              <select id="health-glucoseType" v-model="healthForm.glucoseType" class="input">
                <option value="">未填写</option>
                <option value="fasting">空腹</option>
                <option value="random">随机</option>
                <option value="postprandial">餐后</option>
              </select>
            </div>
            <div class="form-group">
              <label class="form-label" for="health-measuredAt">测量时间</label>
              <input id="health-measuredAt" v-model="healthForm.measuredAt" class="input" type="datetime-local">
            </div>
            <div class="form-group wide">
              <label class="form-label" for="health-pastHistory">既往史</label>
              <textarea id="health-pastHistory" v-model="healthForm.pastHistory" class="input" rows="3" maxlength="2000" placeholder="例如：高血压 5 年，阑尾切除术后"></textarea>
            </div>
            <div class="form-group wide">
              <label class="form-label" for="health-familyHistory">家族史</label>
              <textarea id="health-familyHistory" v-model="healthForm.familyHistory" class="input" rows="3" maxlength="2000" placeholder="例如：父亲高血压，母亲 2 型糖尿病"></textarea>
            </div>
            <div class="form-group wide">
              <label class="form-label" for="health-personalHistory">个人史</label>
              <textarea id="health-personalHistory" v-model="healthForm.personalHistory" class="input" rows="3" maxlength="2000" placeholder="例如：偶尔饮酒，不吸烟"></textarea>
            </div>
            <button class="btn btn--primary" type="submit" :disabled="healthSaving">{{ healthSaving ? '保存中…' : '保存健康档案' }}</button>
          </form>
          <div v-else-if="health?.exists" class="vue-info">
            <div><small>身高</small><b>{{ health.heightCm ? `${health.heightCm} cm` : '—' }}</b></div>
            <div><small>体重</small><b>{{ health.weightKg ? `${health.weightKg} kg` : '—' }}</b></div>
            <div><small>BMI</small><b>{{ healthBmi || '—' }}</b></div>
            <div><small>血压</small><b>{{ healthBloodPressure ? `${healthBloodPressure} mmHg` : '—' }}</b></div>
            <div><small>血糖</small><b>{{ health.glucoseMmol ? `${health.glucoseMmol} mmol/L ${formatGlucoseType(health.glucoseType)}`.trim() : '—' }}</b></div>
            <div><small>心率</small><b>{{ health.heartRateBpm ? `${health.heartRateBpm} 次/分` : '—' }}</b></div>
            <div class="wide"><small>测量时间</small><b>{{ formatDateTime(health.measuredAt) || '—' }}</b></div>
            <div class="wide"><small>既往史</small><b>{{ health.pastHistory || '未填写' }}</b></div>
            <div class="wide"><small>家族史</small><b>{{ health.familyHistory || '未填写' }}</b></div>
            <div class="wide"><small>个人史</small><b>{{ health.personalHistory || '未填写' }}</b></div>
          </div>
          <div v-else class="vue-record-empty">
            <strong>还没有健康档案</strong>
            <p>补充身高、血压、血糖和病史，方便后续问诊对照。</p>
            <button class="btn btn--primary btn--sm" type="button" @click="healthEditing = true">填写健康档案</button>
          </div>
          <div v-if="snapshots.length" class="vue-snapshots">
            <h4>历史快照</h4>
            <article v-for="item in snapshots" :key="item.id" class="vue-snapshot-row">
              <div>
                <strong>{{ formatDateTime(item.measuredAt) || '未标注测量时间' }}</strong>
                <span>
                  {{ item.heightCm ? `${item.heightCm} cm` : '身高未填' }}
                  · {{ item.weightKg ? `${item.weightKg} kg` : '体重未填' }}
                  · {{ formatBloodPressure(item.systolicMmhg, item.diastolicMmhg) || '血压未填' }}
                </span>
              </div>
              <button class="btn btn--danger btn--sm" type="button" @click="removeSnapshot(item)">删除</button>
            </article>
          </div>
        </div>
      </section>

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
  </div>
</template>

<style scoped>
.vue-message{text-align:center;color:var(--c-danger)}.vue-message.success{color:var(--c-success)}.vue-profile{display:flex;gap:24px}.vue-profile-card{width:240px;text-align:center;padding:32px 24px;flex-shrink:0}.vue-profile-card h2{font-family:var(--font-serif);margin:12px 0 4px}.vue-profile-card p{color:var(--c-muted)}.vue-profile-main{flex:1}.vue-info,.vue-form{display:grid;grid-template-columns:1fr 1fr;gap:14px 28px}.vue-info small,.vue-info b{display:block}.vue-info small{color:var(--c-muted)}.vue-info .wide,.vue-form .wide,.vue-health-form .wide{grid-column:1/-1}
.vue-health,.vue-my-registrations{margin-top:24px}.vue-health .clinic-panel__head,.vue-my-registrations .clinic-panel__head{align-items:center}.vue-health .clinic-panel__head p,.vue-my-registrations .clinic-panel__head p{margin:4px 0 0;color:var(--color-text-secondary);font-size:13px;font-weight:400}.vue-health-actions{display:flex;gap:8px;flex-shrink:0}.vue-health-form textarea.input{min-height:88px;resize:vertical}.vue-snapshots{margin-top:20px;padding-top:16px;border-top:1px solid var(--color-border)}.vue-snapshots h4{margin:0 0 10px;font-size:14px}.vue-snapshot-row{display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:center;gap:16px;padding:12px 0;border-bottom:1px solid var(--color-border)}.vue-snapshot-row:last-child{border-bottom:0;padding-bottom:0}.vue-snapshot-row strong,.vue-snapshot-row span{display:block}.vue-snapshot-row span{margin-top:4px;color:var(--color-text-secondary);font-size:13px}
.vue-record-count{color:var(--color-brand-700);font-size:13px;font-weight:750}.vue-registration-list{display:grid}.vue-registration-row{display:grid;grid-template-columns:minmax(0,1fr) auto auto;align-items:center;gap:16px;padding:15px 0;border-bottom:1px solid var(--color-border)}.vue-registration-row:first-child{padding-top:0}.vue-registration-row:last-child{border-bottom:0;padding-bottom:0}.vue-registration-row strong,.vue-registration-row span,.vue-registration-row small{display:block}.vue-registration-row span{margin-top:4px;color:var(--color-text-secondary);font-size:14px}.vue-registration-row small{margin-top:4px;color:var(--color-text-muted);font-size:12px}.vue-registration-actions{display:flex;gap:8px}.vue-record-empty{display:grid;justify-items:start;gap:8px;padding:8px 0}.vue-record-empty p{margin:0;color:var(--color-text-secondary);font-size:14px}.vue-record-hint{margin:14px 0 0;color:var(--color-text-secondary);font-size:13px}.vue-record-error{margin:0;color:var(--color-danger)}
@media(max-width:700px){.vue-profile{flex-direction:column}.vue-profile-card{width:auto}.vue-info,.vue-form{grid-template-columns:1fr 1fr}.vue-health .clinic-panel__head{align-items:flex-start}.vue-health-actions{flex-wrap:wrap;justify-content:flex-end}.vue-registration-row,.vue-snapshot-row{grid-template-columns:1fr auto;align-items:start}.vue-registration-row>.shared-status{grid-column:2;grid-row:1}.vue-registration-actions{grid-column:1/-1}}
</style>
