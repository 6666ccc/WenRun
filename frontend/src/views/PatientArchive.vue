<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuth } from '../stores'
import {
  cancelRegistration,
  createHealthProfile,
  getHealthProfile,
  getPatient,
  listRegistrations,
  updateHealthProfile,
  updatePatient,
} from '../api'
import { updateProfile } from '../api/modules/user'
import { archiveDialogFromQuery, archiveTabFromQuery } from '../features/archive/tabs'
import { emptyHealthForm, fillHealthForm, isMetricEditor, metricEditor, toHealthPayload } from '../utils/healthProfile'
import { useIsPc } from '../composables/useIsPc'
import UiState from '../components/UiState.vue'
import MobileTabbar from '../components/MobileTabbar.vue'
import ArchiveSidebar from '../components/archive/ArchiveSidebar.vue'
import ArchiveHealthData from '../components/archive/ArchiveHealthData.vue'
import ArchiveBasicInfo from '../components/archive/ArchiveBasicInfo.vue'
import ArchiveHealthInfo from '../components/archive/ArchiveHealthInfo.vue'
import ArchiveRegistrations from '../components/archive/ArchiveRegistrations.vue'
import ArchiveDocuments from '../components/archive/ArchiveDocuments.vue'
import ArchiveUnavailable from '../components/archive/ArchiveUnavailable.vue'

const TABS = [
  { id: 'health', label: '健康数据' },
  { id: 'activity', label: '运动睡眠' },
  { id: 'documents', label: '就医资料' },
  { id: 'registrations', label: '我的挂号' },
]

const route = useRoute()
const router = useRouter()
const isPc = useIsPc()
const { user, updateUser, activePatientId } = useAuth()
const patient = ref(null)
const health = ref(null)
const registrations = ref([])
const loading = ref(true)
const error = ref('')
const healthError = ref('')
const recordsError = ref('')
const saving = ref(false)
const healthSaving = ref(false)
const message = ref('')
const notice = ref('')
const editor = ref(archiveDialogFromQuery(route.query.tab))
const healthForm = reactive(emptyHealthForm())

const tab = computed(() => archiveTabFromQuery(route.query.tab))
const dialog = computed(() => archiveDialogFromQuery(route.query.tab))

function openTab(id) {
  if (id === 'basic' || id === 'history') {
    editor.value = id
    router.replace({ path: '/archive', query: { tab: id } })
    return
  }
  editor.value = ''
  router.replace({ path: '/archive', query: id === 'health' ? {} : { tab: id } })
}

function closeEditor() {
  editor.value = ''
  if (dialog.value) router.replace({ path: '/archive' })
}

function isTabActive(id) {
  return tab.value === id
}

function fillHealth(data) {
  Object.assign(healthForm, fillHealthForm(data || {}))
}

async function load() {
  const patientId = activePatientId.value
  if (!patientId) return void (loading.value = false)
  try {
    const [profile, healthProfile, records] = await Promise.allSettled([
      getPatient(patientId),
      getHealthProfile(patientId),
      listRegistrations({ patientId }),
    ])
    if (profile.status === 'fulfilled') patient.value = profile.value
    else error.value = profile.reason?.message || '档案加载失败'
    if (healthProfile.status === 'fulfilled') {
      health.value = healthProfile.value
      fillHealth(health.value)
    } else {
      healthError.value = healthProfile.reason?.message || '健康档案加载失败'
    }
    if (records.status === 'fulfilled') registrations.value = records.value || []
    else recordsError.value = records.reason?.message || '挂号记录加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(load)
watch(activePatientId, () => {
  loading.value = true
  load()
})

watch(() => route.query.tab, (value) => {
  const next = archiveDialogFromQuery(value)
  if (next) editor.value = next
  else if (editor.value === 'basic' || editor.value === 'history') editor.value = ''
})
watch(editor, (value) => {
  if (!isMetricEditor(value)) return
  message.value = ''
  fillHealth(health.value)
})

async function savePatient(form) {
  saving.value = true
  message.value = ''
  try {
    await updatePatient(activePatientId.value, form)
    try { await updateProfile({ ...form }) } catch { /* 患者档案已保存 */ }
    patient.value = await getPatient(activePatientId.value)
    if (form.name && form.name !== user.value.realName) updateUser({ realName: form.name })
    message.value = '资料已保存'
    closeEditor()
  } catch (nextError) {
    message.value = nextError.message || '保存失败'
  } finally {
    saving.value = false
  }
}

async function saveHealth(patch = {}) {
  healthSaving.value = true
  message.value = ''
  try {
    Object.assign(healthForm, patch)
    if (!healthForm.measuredAt) {
      const now = new Date()
      const pad = (n) => String(n).padStart(2, '0')
      healthForm.measuredAt = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}T${pad(now.getHours())}:${pad(now.getMinutes())}`
    }
    const payload = toHealthPayload(healthForm)
    const saved = health.value?.exists
      ? await updateHealthProfile(activePatientId.value, payload)
      : await createHealthProfile(activePatientId.value, payload)
    health.value = saved
    fillHealth(saved)
    closeEditor()
    message.value = '健康档案已保存'
  } catch (nextError) {
    message.value = nextError.message || '健康档案保存失败'
  } finally {
    healthSaving.value = false
  }
}

function showUnavailable(label) {
  notice.value = `${label}暂未开放，我们正在完善这项能力。`
}

async function cancel(item) {
  try {
    await cancelRegistration(item.id)
    await load()
    message.value = '挂号已取消'
  } catch (nextError) {
    message.value = nextError.message || '取消挂号失败'
  }
}

const editorTitle = computed(() => {
  if (editor.value === 'basic') return '基本资料'
  if (editor.value === 'history') return '健康信息'
  return metricEditor(editor.value)?.title || '记录数据'
})

const metricFields = computed(() => metricEditor(editor.value)?.fields || [])
</script>

<template>
  <div class="archive-page">
    <div class="archive">
      <UiState :loading="loading" :error="error" :empty="!patient" empty-text="暂无患者档案">
        <ArchiveSidebar
          :patient="patient"
          @open-tab="openTab"
          @unavailable="showUnavailable"
          @register="router.push('/registration')"
        />
        <div class="archive__main">
          <p v-if="notice" class="archive-banner" role="status">{{ notice }}</p>
          <p v-else-if="message && tab === 'health'" class="archive-banner archive-banner--ok" role="status">{{ message }}</p>
          <nav class="archive-tabs" aria-label="档案栏目">
            <button
              v-for="item in TABS"
              :key="item.id"
              type="button"
              :class="{ 'is-active': isTabActive(item.id) }"
              @click="openTab(item.id)"
            >{{ item.label }}</button>
          </nav>

          <ArchiveHealthData
            v-if="tab === 'health'"
            :patient="patient"
            :health="health"
            :patient-id="activePatientId"
            :error="healthError"
            @record="editor = $event"
            @unavailable="showUnavailable"
            @open-tab="openTab"
          />
          <ArchiveUnavailable v-else-if="tab === 'activity'" title="运动睡眠" hint="暂未接入运动与睡眠数据，后续将支持手动记录或设备同步。" />
          <ArchiveDocuments v-else-if="tab === 'documents'" @unavailable="showUnavailable" />
          <ArchiveRegistrations v-else :registrations="registrations" :error="recordsError" @cancel="cancel" />
        </div>
      </UiState>

      <div v-if="editor" class="archive-dialog-overlay" role="presentation" @click.self="closeEditor">
        <div class="archive-dialog" :class="{ 'archive-dialog--form': editor === 'basic' || editor === 'history' }">
          <ArchiveBasicInfo
            v-if="editor === 'basic'"
            :patient="patient"
            :saving="saving"
            :message="message"
            @save="savePatient"
            @cancel="closeEditor"
          />
          <ArchiveHealthInfo
            v-else-if="editor === 'history'"
            :health="health"
            :saving="healthSaving"
            :error="healthError"
            :message="message"
            @save="saveHealth"
            @cancel="closeEditor"
          />
          <form v-else-if="isMetricEditor(editor)" @submit.prevent="saveHealth()">
            <h3>{{ editorTitle }}</h3>
            <p v-if="message" class="archive-panel__error" role="alert">{{ message }}</p>
            <label v-for="field in metricFields" :key="field.key">
              {{ field.label }}
              <select v-if="field.type === 'select'" v-model="healthForm[field.key]" class="input">
                <option v-for="option in field.options" :key="option.value" :value="option.value">{{ option.label }}</option>
              </select>
              <input
                v-else
                v-model="healthForm[field.key]"
                class="input"
                :type="field.type"
                :step="field.step"
                :min="field.min"
                :max="field.max"
              >
            </label>
            <label>测量时间<input v-model="healthForm.measuredAt" class="input" type="datetime-local"></label>
            <div class="archive-dialog__actions">
              <button class="btn btn--ghost" type="button" @click="closeEditor">取消</button>
              <button class="btn btn--primary" type="submit" :disabled="healthSaving">{{ healthSaving ? '保存中…' : '保存' }}</button>
            </div>
          </form>
        </div>
      </div>
    </div>
    <MobileTabbar v-if="!isPc" />
  </div>
</template>

<style scoped>
.archive-page { min-height: 100dvh; background: var(--color-bg); }
.archive {
  display: grid;
  grid-template-columns: minmax(240px, 280px) minmax(0, 1fr);
  gap: 20px;
  min-height: 100dvh;
  padding: 24px 28px 36px;
  background: var(--color-bg);
}
.archive :deep(.shared-loading),
.archive :deep(.ui-state),
.archive :deep(.shared-empty) {
  grid-column: 1 / -1;
}
.archive__main { min-width: 0; display: grid; align-content: start; gap: 16px; }
.archive-banner {
  margin: 0;
  padding: 10px 14px;
  border-radius: 12px;
  background: var(--color-warning-bg);
  color: var(--color-warning);
  font-size: 13px;
  font-weight: 700;
}
.archive-banner--ok { background: var(--color-success-bg); color: var(--color-success); }
.archive-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 18px;
  padding: 0 6px 8px;
  border-bottom: 1px solid var(--color-border);
}
.archive-tabs button {
  position: relative;
  padding: 10px 2px 12px;
  border: 0;
  background: transparent;
  color: var(--color-text-secondary);
  font: inherit;
  font-size: 15px;
  cursor: pointer;
  transition: color var(--motion-fast) ease;
}
.archive-tabs button.is-active { color: var(--color-brand-800); font-weight: 750; }
.archive-tabs button.is-active::after {
  content: '';
  position: absolute;
  left: 0; right: 0; bottom: -9px;
  height: 3px;
  border-radius: 99px;
  background: var(--color-brand-700);
  animation: archive-tab-in var(--motion-emphasis) var(--ease-clinical) both;
}
.archive-dialog-overlay {
  position: fixed;
  inset: 0;
  z-index: 40;
  display: grid;
  place-items: center;
  padding: 24px;
  background: rgba(23, 52, 59, .28);
}
.archive-dialog {
  width: min(440px, 100%);
  display: grid;
  gap: 12px;
  padding: 22px;
  border-radius: 18px;
  background: #fff;
  max-height: min(88dvh, 760px);
  overflow: auto;
}
.archive-dialog--form { width: min(520px, 100%); }
.archive-dialog h3 { margin: 0; }
.archive-dialog form, .archive-dialog .archive-form { display: grid; gap: 12px; }
.archive-dialog label { display: grid; gap: 6px; color: var(--color-text-secondary); font-size: 13px; }
.archive-dialog__actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 8px; }
@media (max-width: 767px) {
  .archive { grid-template-columns: 1fr; padding: 16px 14px calc(28px + 64px + env(safe-area-inset-bottom)); }
}
</style>

<style>
.archive-panel {
  position: relative;
  overflow: hidden;
  padding: 18px 18px 16px;
  border: 1px solid var(--color-border);
  border-radius: 20px;
  background: #fff;
  box-shadow: var(--shadow-xs);
  transition: border-color var(--motion-fast) ease, box-shadow var(--motion-fast) ease, transform var(--motion-fast) var(--ease-clinical);
}
.archive-panel::before { content: ''; position: absolute; inset: 0 0 auto; height: 1px; background: linear-gradient(90deg, transparent, rgba(15,143,130,.34), transparent); opacity: .65; }
.archive-panel:hover { border-color: var(--color-border-strong); box-shadow: var(--shadow-clinical); transform: translateY(-1px); }
.archive-panel header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 16px;
}
.archive-panel h2 { margin: 0; font-size: 16px; }
.archive-panel header p, .archive-panel__hint { margin: 4px 0 0; color: var(--color-text-secondary); font-size: 13px; }
.archive-panel__count { color: var(--color-brand-700); font-size: 13px; font-weight: 750; }
.archive-panel__msg { margin: 0 0 12px; color: var(--color-success); }
.archive-panel__error { margin: 0 0 12px; color: var(--color-danger); }
.archive-form { display: grid; gap: 12px; }
.archive-form label { display: grid; gap: 6px; color: var(--color-text-secondary); font-size: 13px; }
.archive-link {
  border: 0; background: transparent; color: var(--color-brand-700);
  font: inherit; font-size: 13px; font-weight: 700; cursor: pointer;
}
.archive-empty { display: grid; justify-items: start; gap: 8px; }
.archive-empty p { margin: 0; color: var(--color-text-secondary); }
.archive-regs { display: grid; }
.archive-regs article {
  display: grid; grid-template-columns: minmax(0, 1fr) auto auto; align-items: center; gap: 16px;
  padding: 14px 0; border-bottom: 1px solid var(--color-border);
}
.archive-regs article:last-child { border-bottom: 0; }
.archive-regs strong, .archive-regs span, .archive-regs small { display: block; }
.archive-regs span { margin-top: 4px; color: var(--color-text-secondary); font-size: 14px; }
.archive-regs small { margin-top: 4px; color: var(--color-text-muted); font-size: 12px; }
.archive-regs__actions { display: flex; gap: 8px; }
.health-data { display: grid; gap: 16px; }
.metric-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr)) 160px;
  gap: 12px;
}
.vital-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
.doc-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }
.basic-list { display: grid; gap: 8px; margin: 0; }
.basic-list > div { display: grid; grid-template-columns: 72px minmax(0, 1fr); gap: 8px; font-size: 13px; }
.basic-list dt { color: var(--color-text-muted); }
.basic-list dd { margin: 0; color: var(--color-text); word-break: break-all; }
.archive-form__grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.metric-card, .metric-cta, .doc-card {
  display: flex; align-items: center; gap: 10px;
  min-height: 84px; padding: 12px 14px;
  border: 1px solid var(--color-border); border-radius: 16px; background: var(--color-surface-soft);
  transition: border-color var(--motion-fast) ease, background-color var(--motion-fast) ease, box-shadow var(--motion-fast) ease, transform var(--motion-fast) var(--ease-clinical);
}
.metric-card--wide { min-height: 72px; }
.metric-card--shell { opacity: .92; }
.metric-card strong, .metric-cta strong { display: block; font-size: 18px; }
.metric-card small, .metric-cta small, .doc-card small, .history-list small {
  display: block; color: var(--color-text-secondary); font-size: 12px;
}
.metric-card em { font-style: normal; color: var(--color-text-muted); font-size: 12px; font-weight: 500; }
.metric-card__warn { display: block; margin-top: 4px; color: var(--color-warning); font-size: 11px; font-weight: 700; }
.metric-card > button {
  margin-left: auto; width: 28px; height: 28px; border: 0; border-radius: 50%;
  background: #fff; color: var(--color-brand-700); cursor: pointer;
}
.metric-cta { flex-direction: column; align-items: flex-start; justify-content: center; text-align: left; cursor: pointer; font: inherit; grid-column: 4; grid-row: 1 / span 2; }
.metric-card__icon {
  width: 36px; height: 36px; display: grid; place-items: center; flex: 0 0 36px; border-radius: 12px;
}
.is-blue { background: #e8f1ff; color: #3b6fd4; }
.is-violet { background: #eee8ff; color: #6b5ce7; }
.is-amber { background: #fff1dd; color: #c47a1a; }
.is-rose, .is-red, .is-pink { background: #ffe8ea; color: #d4535e; }
.is-sky { background: #e7f6ff; color: #2f8fbf; }
.is-green { background: #e7f6ee; color: #17623e; }
.doc-card { flex-direction: column; align-items: flex-start; cursor: pointer; font: inherit; text-align: left; }
.history-list { display: grid; gap: 8px; }
.history-list button {
  display: flex; gap: 10px; align-items: center; width: 100%; padding: 10px 8px;
  border: 0; border-radius: 12px; background: transparent; text-align: left; font: inherit; cursor: pointer;
}
.metric-card:hover, .metric-card:focus-within, .doc-card:hover, .doc-card:focus-visible, .metric-cta:hover, .metric-cta:focus-visible { border-color: var(--color-border-strong); background: #fff; box-shadow: 0 10px 26px rgba(7,91,85,.08); transform: translateY(-1px); }
.history-list button { transition: background-color var(--motion-fast) ease, transform var(--motion-fast) var(--ease-clinical); }
.history-list button:hover, .history-list button:focus-visible { background: var(--color-mint-050); transform: translateX(2px); }
@keyframes archive-tab-in { from { opacity: 0; transform: scaleX(.25); } to { opacity: 1; transform: scaleX(1); } }
@media (max-width: 1100px) {
  .metric-grid, .vital-grid, .doc-grid { grid-template-columns: 1fr 1fr; }
  .metric-cta { grid-column: 1 / -1; }
}
@media (max-width: 767px) {
  .archive-regs article { grid-template-columns: 1fr auto; }
  .archive-regs__actions { grid-column: 1 / -1; }
  .archive-form__grid { grid-template-columns: 1fr; }
}
@media (prefers-reduced-motion: reduce) {
  .archive-panel, .metric-card, .metric-cta, .doc-card, .history-list button { transition: none; transform: none; }
  .archive-tabs button.is-active::after { animation: none; }
}
</style>
