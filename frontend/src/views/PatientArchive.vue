<script setup>
import { computed, defineAsyncComponent, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
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
import UiIcon from '../components/UiIcon.vue'
import MobileTabbar from '../components/MobileTabbar.vue'
import ArchiveSidebar from '../components/archive/ArchiveSidebar.vue'
import ArchiveHealthData from '../components/archive/ArchiveHealthData.vue'
import ArchiveTrendSkeleton from '../components/archive/ArchiveTrendSkeleton.vue'
import ArchiveBasicInfo from '../components/archive/ArchiveBasicInfo.vue'
import ArchiveHealthInfo from '../components/archive/ArchiveHealthInfo.vue'
import ArchiveRegistrations from '../components/archive/ArchiveRegistrations.vue'
import ArchiveDocuments from '../components/archive/ArchiveDocuments.vue'
import ArchiveActivity from '../components/archive/ArchiveActivity.vue'

const TABS = [
  { id: 'health', label: '健康数据', icon: 'activity' },
  { id: 'trend', label: '健康趋势', icon: 'history' },
  { id: 'activity', label: '运动睡眠', icon: 'heart' },
  { id: 'documents', label: '就医资料', icon: 'record' },
  { id: 'registrations', label: '我的挂号', icon: 'calendar' },
]
const ArchiveHealthTrend = defineAsyncComponent({
  loader: () => import('../components/archive/ArchiveHealthTrend.vue'),
  loadingComponent: ArchiveTrendSkeleton,
  delay: 80,
})

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
const FACE_TURN = 360 / TABS.length
const prismDepth = ref(0)
const stageHeight = ref(0)
const stageElement = ref(null)
const faceElements = new Map()
let stageObserver
let faceObserver
const healthForm = reactive(emptyHealthForm())

const tab = computed(() => archiveTabFromQuery(route.query.tab))
const dialog = computed(() => archiveDialogFromQuery(route.query.tab))

function rotationForTab(id) {
  const index = Math.max(0, TABS.findIndex((item) => item.id === id))
  return -index * FACE_TURN
}

function nearestRotation(current, target) {
  return target + Math.round((current - target) / 360) * 360
}

const prismRotation = ref(rotationForTab(tab.value))

function openTab(id) {
  if (id === 'basic' || id === 'history') {
    editor.value = id
    router.replace({ path: '/archive', query: { tab: id } })
    return
  }
  editor.value = ''
  router.replace({ path: '/archive', query: id === 'health' ? {} : { tab: id } })
}

function updateStageGeometry() {
  if (!stageElement.value) return
  prismDepth.value = Math.round(stageElement.value.clientWidth / (2 * Math.tan(Math.PI / TABS.length)))
  const activeFace = faceElements.get(tab.value)
  if (activeFace) stageHeight.value = Math.ceil(activeFace.offsetHeight)
}

function setFaceElement(id, element) {
  if (!element) {
    faceElements.delete(id)
    return
  }
  faceElements.set(id, element)
  faceObserver?.observe(element)
  nextTick(updateStageGeometry)
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
onMounted(() => {
  stageObserver = new ResizeObserver(updateStageGeometry)
  faceObserver = new ResizeObserver(updateStageGeometry)
  if (stageElement.value) stageObserver.observe(stageElement.value)
  faceElements.forEach((element) => faceObserver.observe(element))
  nextTick(updateStageGeometry)
})
onBeforeUnmount(() => {
  stageObserver?.disconnect()
  faceObserver?.disconnect()
})
watch(stageElement, (element, previous) => {
  if (previous) stageObserver?.unobserve(previous)
  if (element) stageObserver?.observe(element)
  nextTick(updateStageGeometry)
})
watch(tab, (next) => {
  prismRotation.value = nearestRotation(prismRotation.value, rotationForTab(next))
  nextTick(updateStageGeometry)
})
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
    <header class="archive-topbar">
      <RouterLink class="archive-brand" to="/home" aria-label="温润医院患者服务首页">
        <span class="archive-brand__mark" aria-hidden="true"><UiIcon name="heart" :size="20" /></span>
        <span>温润医院<small>WENRUN CARE</small></span>
      </RouterLink>
      <div class="archive-topbar__right">
        <span class="archive-topbar__caption">用心记录每一次健康变化</span>
        <RouterLink class="archive-topbar__back" to="/home"><UiIcon name="arrowLeft" :size="15" />返回首页</RouterLink>
      </div>
    </header>
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
          <p v-else-if="message && tab === 'health' && !editor" class="archive-banner archive-banner--ok" role="status">{{ message }}</p>
          <nav class="archive-tabs" aria-label="档案栏目">
            <button
              v-for="item in TABS"
              :key="item.id"
              type="button"
              :class="{ 'is-active': isTabActive(item.id) }"
              :aria-current="isTabActive(item.id) ? 'page' : undefined"
              @click="openTab(item.id)"
            >
              <UiIcon :name="item.icon" :size="16" />
              {{ item.label }}
            </button>
          </nav>

          <div ref="stageElement" class="archive-stage" :style="{ height: stageHeight ? `${stageHeight}px` : undefined }">
            <div class="archive-prism" :style="{ transform: `translateZ(-${prismDepth}px) rotateY(${prismRotation}deg)` }">
              <div
                v-for="(item, index) in TABS"
                :key="item.id"
                :ref="(element) => setFaceElement(item.id, element)"
                class="archive-face archive-pane"
                :class="{ 'is-active': tab === item.id }"
                :style="{ transform: `rotateY(${index * FACE_TURN}deg) translateZ(${prismDepth}px)` }"
                :aria-hidden="tab !== item.id"
                :inert="tab !== item.id"
              >
                <ArchiveHealthData
                  v-if="item.id === 'health'"
                  :health="health"
                  :error="healthError"
                  @record="editor = $event"
                  @unavailable="showUnavailable"
                  @open-tab="openTab"
                />
                <ArchiveHealthTrend
                  v-else-if="item.id === 'trend'"
                  :patient-id="activePatientId"
                  :refresh-key="`${activePatientId}:${health?.updateTime || health?.measuredAt || ''}`"
                />
                <ArchiveActivity v-else-if="item.id === 'activity'" :patient-id="activePatientId" />
                <ArchiveDocuments v-else-if="item.id === 'documents'" @unavailable="showUnavailable" />
                <ArchiveRegistrations v-else :registrations="registrations" :error="recordsError" @cancel="cancel" />
              </div>
            </div>
          </div>
        </div>
      </UiState>

      <Transition name="archive-pop">
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
      </Transition>
    </div>
    <MobileTabbar v-if="!isPc" />
  </div>
</template>

<style scoped>
.archive-page {
  min-height: 100dvh;
  padding: 26px 32px 64px;
  background:
    radial-gradient(ellipse at 2% 5%, rgba(210, 234, 226, .42), transparent 34rem),
    #f7f9f7;
}
.archive-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  max-width: 1448px;
  margin: 0 auto 28px;
}
.archive-brand {
  display: inline-flex;
  align-items: center;
  gap: 11px;
  color: #074d48;
  font-size: 20px;
  font-weight: 800;
  letter-spacing: -.03em;
  text-decoration: none;
}
.archive-brand small {
  margin-left: 6px;
  color: #8da9a3;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: .16em;
}
.archive-brand__mark {
  display: grid;
  place-items: center;
  width: 36px;
  height: 36px;
  border-radius: 12px;
  color: #fff;
  background: linear-gradient(145deg, #0c796e, #07544e);
  box-shadow: 0 7px 15px rgba(7, 84, 78, .18);
}
.archive-topbar__right { display: flex; align-items: center; gap: 16px; }
.archive-topbar__caption { color: #81938e; font-size: 12px; letter-spacing: .04em; }
.archive-topbar__back {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  color: #0b655d;
  font-size: 13px;
  font-weight: 700;
  text-decoration: none;
}
.archive {
  display: grid;
  grid-template-columns: 258px minmax(0, 1fr);
  align-items: start;
  gap: 34px;
  max-width: 1448px;
  margin: 0 auto;
}
.archive :deep(.shared-loading),
.archive :deep(.ui-state),
.archive :deep(.shared-empty) {
  grid-column: 1 / -1;
}
.archive__main { min-width: 0; display: grid; align-content: start; gap: 0; }
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
  align-items: center;
  gap: 28px;
  margin: 0 0 22px;
  padding: 0 2px;
  border-bottom: 1px solid #dce7e2;
  background: transparent;
}
.archive-tabs button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 58px;
  padding: 0 2px;
  border: 0;
  border-bottom: 2px solid transparent;
  background: transparent;
  color: #778c85;
  font: inherit;
  font-size: 13px;
  font-weight: 700;
  white-space: nowrap;
  cursor: pointer;
  transition: color .2s ease, border-color .2s ease;
}
.archive-tabs button.is-active {
  color: #0b675a;
  border-bottom-color: #0b8878;
}
.archive-tabs button:hover, .archive-tabs button:focus-visible { color: #0b675a; }
.archive-stage { position: relative; min-height: 120px; perspective: 2200px; perspective-origin: 50% 24%; overflow: hidden; transition: height .65s cubic-bezier(.22, 1, .36, 1); }
.archive-prism { position: relative; width: 100%; height: 100%; transform-style: preserve-3d; transition: transform .9s cubic-bezier(.16, 1, .3, 1); will-change: transform; }
.archive-face { position: absolute; top: 0; left: 0; width: 100%; backface-visibility: hidden; transform-style: preserve-3d; }
.archive-face:not(.is-active) { pointer-events: none; }
.archive-pane { display: grid; gap: 16px; }
.archive-pop-enter-active,
.archive-pop-leave-active { transition: opacity .32s cubic-bezier(.22, 1, .36, 1); }
.archive-pop-enter-active .archive-dialog,
.archive-pop-leave-active .archive-dialog {
  transition: opacity .32s cubic-bezier(.22, 1, .36, 1), transform .52s cubic-bezier(.76, 0, .24, 1);
}
.archive-pop-enter-from,
.archive-pop-leave-to { opacity: 0; }
.archive-pop-enter-from .archive-dialog,
.archive-pop-leave-to .archive-dialog { opacity: 0; transform: translateY(18px) scale(.985); }
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
@media (max-width: 1100px) {
  .archive-page { padding: 18px 20px 40px; }
  .archive { grid-template-columns: 235px minmax(0, 1fr); gap: 22px; }
}
@media (max-width: 820px) {
  .archive { grid-template-columns: 1fr; }
  .archive-stage { perspective: none; }
  .archive-prism { transform: none !important; transition: none; }
  .archive-face { transform: none !important; transition: opacity .32s ease, translate .42s cubic-bezier(.22, 1, .36, 1); }
  .archive-face:not(.is-active) { opacity: 0; translate: 24px 0; visibility: hidden; }
  .archive-face.is-active { opacity: 1; translate: 0 0; visibility: visible; }
}
@media (max-width: 767px) {
  .archive-page { padding: 16px 14px calc(28px + 64px + env(safe-area-inset-bottom)); }
  .archive-topbar { margin-bottom: 16px; }
  .archive-brand { font-size: 17px; }
  .archive-brand small, .archive-topbar__caption { display: none; }
  .archive-tabs { overflow-x: auto; scrollbar-width: none; }
  .archive-tabs::-webkit-scrollbar { display: none; }
  .archive-tabs button { min-height: 54px; }
}
@media (prefers-reduced-motion: reduce) {
  .archive-stage, .archive-prism, .archive-face { transition: none; }
  .archive-prism { transform: none !important; }
  .archive-face { transform: none !important; }
  .archive-face:not(.is-active) { display: none; }
  .archive-pop-enter-active,
  .archive-pop-leave-active,
  .archive-pop-enter-active .archive-dialog,
  .archive-pop-leave-active .archive-dialog { transition-duration: 1ms; }
}
</style>

<style>
.archive-panel {
  position: relative;
  padding: 26px 28px 28px;
  border: 1px solid #e0e9e4;
  border-radius: 18px;
  background: #fff;
  box-shadow: 0 10px 30px rgba(35, 80, 68, .04);
}
.archive-panel header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 22px;
}
.archive-panel h2 { margin: 0; color: #193f38; font-size: 19px; font-weight: 760; letter-spacing: -.035em; }
.archive-panel header p, .archive-panel__hint { margin: 6px 0 0; color: #8a9e95; font-size: 12px; }
.archive-section__index { color: #a8bcb3; font-size: 10px; font-weight: 800; letter-spacing: .16em; white-space: nowrap; }
.archive-panel header > div:first-child { display: flex; align-items: flex-start; gap: 10px; }
.archive-panel header > div:first-child::before {
  content: "";
  width: 3px;
  height: 29px;
  flex: none;
  margin-top: 2px;
  border-radius: 3px;
  background: #22a390;
}
.archive-panel__count { color: var(--color-brand-700); font-size: 13px; font-weight: 750; }
.archive-panel__msg { margin: 0 0 12px; color: var(--color-success); }
.archive-panel__error { margin: 0 0 12px; color: var(--color-danger); }
.archive-form { display: grid; gap: 12px; }
.archive-form label { display: grid; gap: 6px; color: var(--color-text-secondary); font-size: 13px; }
.archive-link {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  border: 0;
  background: transparent;
  color: #0e8175;
  font: inherit;
  font-size: 12px;
  font-weight: 800;
  cursor: pointer;
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
.health-data { display: grid; gap: 18px; }
.metric-grid, .vital-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }
.metric-grid--quiet { grid-template-columns: repeat(2, minmax(0, 1fr)); margin-top: 10px; }
.doc-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }
.basic-list { display: grid; gap: 8px; margin: 0; }
.basic-list > div { display: grid; grid-template-columns: 72px minmax(0, 1fr); gap: 8px; font-size: 13px; }
.basic-list dt { color: var(--color-text-muted); }
.basic-list dd { margin: 0; color: var(--color-text); word-break: break-all; }
.archive-form__grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.metric-card {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  min-height: 154px;
  padding: 18px 19px;
  border: 1px solid #e5ede8;
  border-radius: 12px;
  background: #fbfcfa;
  transition: border-color .2s ease, background .2s ease;
}
.metric-card::after { display: none; }
.metric-card__head { display: flex; align-items: center; gap: 8px; width: 100%; }
.metric-card__label { color: #4c6e64; font-size: 12px; font-weight: 720; }
.metric-card__icon {
  width: 28px; height: 28px; display: grid; place-items: center; flex: none; border-radius: 8px; background: #e6f3ed; color: #248a77;
}
.metric-card__head button {
  display: grid; place-items: center; width: 29px; height: 29px; margin-left: auto; padding: 0;
  border: 1px solid #d6e6de; border-radius: 8px; background: #fff; color: #0c7767; cursor: pointer;
  transition: border-color .2s ease, background .2s ease;
}
.metric-card__head button:hover, .metric-card__head button:focus-visible { border-color: #6db5a4; background: #eaf7f1; }
.metric-card strong {
  margin-top: 22px;
  color: #183d36;
  font-size: 32px;
  line-height: 1;
  font-weight: 760;
  letter-spacing: -.055em;
  font-variant-numeric: tabular-nums;
}
.metric-card em, .metric-card strong small { margin-left: 5px; color: #7d948a; font-size: 12px; font-style: normal; font-weight: 650; letter-spacing: 0; }
.metric-card__foot { margin-top: auto; padding-top: 10px; color: #879c91; font-size: 11px; }
.metric-card__warn { color: #93aaa3; }
.metric-card--featured { border-color: #d4e9dc; background: #eaf4ed; color: #193f38; }
.metric-card--featured .metric-card__icon { background: #d5e9dc; color: #15725f; }
.metric-card--featured .metric-card__label,
.metric-card--featured strong,
.metric-card--featured .metric-card__foot { color: #386a59; }
.metric-card--quiet { min-height: 112px; background: #fff; }
.metric-card--quiet strong { margin-top: 13px; font-size: 22px; color: #a0b5aa; }
.metric-card--quiet .metric-card__icon { background: #f1f5f1; color: #90a79c; }
.vital-grid .metric-card { min-height: 135px; }
.vital-grid .metric-card strong { font-size: 25px; }
.vital-grid .metric-card:nth-child(1) .metric-card__icon,
.vital-grid .metric-card:nth-child(3) .metric-card__icon { background: #fff0ee; color: #cf6c65; }
.vital-grid .metric-card:nth-child(2) .metric-card__icon { background: #fff3e7; color: #bf7d40; }
.vital-grid .metric-card:nth-child(4) .metric-card__icon { background: #e7f6ff; color: #2f8fbf; }
.vital-grid .metric-card:nth-child(5) .metric-card__icon { background: #eee8ff; color: #6b5ce7; }
.vital-grid .metric-card:nth-child(6) .metric-card__icon { background: #fff1dd; color: #c47a1a; }
.metric-card:hover, .metric-card:focus-within { border-color: #a9d3bf; background: #fff; }
.doc-card {
  display: flex; flex-direction: column; align-items: flex-start; gap: 8px;
  min-height: 112px; padding: 16px;
  border: 1px solid #e2eeea; border-radius: 16px; background: #f9fcfb;
  font: inherit; text-align: left; cursor: pointer;
  transition: transform .45s cubic-bezier(.76, 0, .24, 1), box-shadow .35s cubic-bezier(.22, 1, .36, 1);
}
.doc-card small, .history-list small { display: block; color: #849d96; font-size: 12px; }
.doc-card:hover, .doc-card:focus-visible { transform: translateY(-3px); box-shadow: 0 14px 28px rgba(7, 91, 85, .08); }
.history-list { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
.history-list button {
  display: flex; gap: 10px; align-items: flex-start; width: 100%; min-height: 88px; padding: 16px;
  border: 1px solid #e2eeea; border-radius: 15px; background: #f9fcfb; text-align: left; font: inherit; cursor: pointer;
  transition: transform .45s cubic-bezier(.76, 0, .24, 1), background .3s ease;
}
.history-list button:hover, .history-list button:focus-visible { background: #fff; transform: translateY(-3px); }
.history-list strong { display: block; margin-top: 1px; font-size: 13px; }
.history-list p, .history-list small { margin: 5px 0 0; }
@media (max-width: 1100px) {
  .metric-grid, .vital-grid, .doc-grid, .history-list { grid-template-columns: 1fr 1fr; }
}
@media (max-width: 767px) {
  .archive-panel { padding: 19px 16px; }
  .archive-regs article { grid-template-columns: 1fr auto; }
  .archive-regs__actions { grid-column: 1 / -1; }
  .archive-form__grid { grid-template-columns: 1fr; }
  .metric-card { min-height: 126px; padding: 14px; }
  .metric-card strong { font-size: 25px; }
  .metric-grid .metric-card--featured { grid-column: 1 / -1; }
  .history-list button:last-child { grid-column: 1 / -1; }
}
@media (prefers-reduced-motion: reduce) {
  .metric-card, .doc-card, .history-list button { transition: none; transform: none; }
}
</style>
