<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth } from '../stores'
import { getPatient, updatePatient } from '../api'
import { updateProfile } from '../api/modules/user'
import { GENDER_MAP, formatDate } from '../utils'
import AppShell from '../components/AppShell.vue'
import PageHeader from '../components/PageHeader.vue'
import UiState from '../components/UiState.vue'

const router = useRouter()
const { user, updateUser, logout } = useAuth()
const patient = ref(null), loading = ref(true), error = ref(''), editing = ref(false), saving = ref(false), message = ref('')
const form = reactive({ name: '', gender: '', phone: '', idCard: '', birthDate: '', address: '', allergyHistory: '' })
function fill(data) { Object.assign(form, { name: data.name || '', gender: data.gender ?? '', phone: data.phone || '', idCard: data.idCard || '', birthDate: data.birthDate || '', address: data.address || '', allergyHistory: data.allergyHistory || '' }) }
async function load() {
  if (!user.value?.patientId) return void (loading.value = false)
  try { patient.value = await getPatient(user.value.patientId); fill(patient.value) }
  catch (nextError) { error.value = nextError.message || '加载失败' }
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
const fields = [
  ['姓名','name'], ['手机号','phone'], ['身份证号','idCard'], ['出生日期','birthDate'],
  ['地址','address'], ['过敏史','allergyHistory'],
]
</script>

<template>
  <AppShell>
    <PageHeader title="个人中心" subtitle="查看和编辑您的档案信息" />
    <div v-if="message" class="card mb-md vue-message" :class="{success:message.includes('成功')}">{{ message }}</div>
    <UiState :loading="loading" :error="error" :empty="!patient" empty-text="暂无患者档案">
      <div class="vue-profile stagger">
        <aside class="card vue-profile-card">
          <div class="view-avatar-ring"><div class="view-avatar-ring__inner">{{ (patient.name || user?.username || '?')[0] }}</div></div>
          <h2>{{ patient.name || user?.username || '未设置姓名' }}</h2><p>{{ patient.patientNo }}</p>
          <button class="btn btn--danger btn--sm" @click="signOut">退出登录</button>
        </aside>
        <section class="card vue-profile-main">
          <div class="flex-between mb-lg"><h3>档案信息</h3><button class="btn btn--outline btn--sm" @click="editing=!editing">{{ editing ? '取消编辑' : '编辑资料' }}</button></div>
          <div v-if="editing" class="vue-form">
            <div v-for="[label,key] in fields" :key="key" class="form-group"><label class="form-label">{{ label }}</label><input v-model="form[key]" class="input" :placeholder="key==='allergyHistory'?'例如：青霉素过敏':''"></div>
            <div class="form-group"><label class="form-label">性别</label><select v-model="form.gender" class="input"><option value="">请选择</option><option :value="0">女</option><option :value="1">男</option></select></div>
            <button class="btn btn--primary" :disabled="saving" @click="save">{{ saving ? '保存中…' : '保存修改' }}</button>
          </div>
          <div v-else class="vue-info">
            <div><small>姓名</small><b>{{ patient.name || '—' }}</b></div><div><small>性别</small><b>{{ GENDER_MAP[patient.gender] || '未知' }}</b></div>
            <div><small>手机号</small><b>{{ patient.phone || '—' }}</b></div><div><small>身份证号</small><b>{{ patient.idCard || '—' }}</b></div>
            <div><small>出生日期</small><b>{{ formatDate(patient.birthDate) }}</b></div><div><small>地址</small><b>{{ patient.address || '—' }}</b></div>
            <div class="wide"><small>过敏史</small><b>{{ patient.allergyHistory || '无' }}</b></div>
          </div>
        </section>
      </div>
    </UiState>
  </AppShell>
</template>

<style scoped>
.vue-message{text-align:center;color:var(--c-danger)}.vue-message.success{color:var(--c-success)}.vue-profile{display:flex;gap:24px}.vue-profile-card{width:240px;text-align:center;padding:32px 24px;flex-shrink:0}.vue-profile-card h2{font-family:var(--font-serif);margin:12px 0 4px}.vue-profile-card p{color:var(--c-muted)}.vue-profile-main{flex:1}.vue-profile-main h3{margin:0}.vue-info,.vue-form{display:grid;grid-template-columns:1fr 1fr;gap:14px 28px}.vue-info small,.vue-info b{display:block}.vue-info small{color:var(--c-muted)}.vue-info .wide{grid-column:1/-1}
@media(max-width:700px){.vue-profile{flex-direction:column}.vue-profile-card{width:auto}.vue-info,.vue-form{grid-template-columns:1fr 1fr}}
</style>
