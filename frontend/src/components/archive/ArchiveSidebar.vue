<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { GENDER_MAP, formatDate } from '../../utils'
import { calcAge, maskIdCard } from '../../features/archive/tabs'
import { useAuth } from '../../stores'
import UiIcon from '../UiIcon.vue'

const props = defineProps({
  patient: { type: Object, required: true },
})
const emit = defineEmits(['open-tab', 'unavailable', 'register'])
const { patients, activePatientId, setActivePatient } = useAuth()
const showSwitcher = computed(() => (patients.value || []).length > 1)
const showPrivate = ref(false)
const sidebarElement = ref(null)
const profileCardElement = ref(null)
const quickCardElement = ref(null)
let privacyTimer
let motionFrame = 0
let reducedMotion
let sidebarResizeObserver

function clampProgress(value) {
  return Math.min(1, Math.max(0, value))
}

function updateScrollMotion() {
  motionFrame = 0
  if (!sidebarElement.value) return

  const viewportHeight = window.innerHeight
  const desktop = window.innerWidth > 820
  sidebarElement.value.style.setProperty('--sidebar-sticky-top', `${Math.min(18, viewportHeight - sidebarElement.value.offsetHeight - 18)}px`)
  if (reducedMotion?.matches) return

  const sidebarTop = sidebarElement.value.getBoundingClientRect().top
  const pageScrollRange = Math.max(1, document.documentElement.scrollHeight - viewportHeight)

  for (const card of [profileCardElement.value, quickCardElement.value]) {
    if (!card) continue
    const cardTop = sidebarTop + card.offsetTop
    const progress = desktop
      ? clampProgress(window.scrollY / pageScrollRange)
      : clampProgress((viewportHeight - cardTop) / (viewportHeight + card.offsetHeight))
    const y = -22 + progress * 44

    card.style.setProperty('--scroll-y', `${y.toFixed(2)}px`)
  }
}

function scheduleScrollMotion() {
  if (!motionFrame) motionFrame = window.requestAnimationFrame(updateScrollMotion)
}

onMounted(() => {
  reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)')
  window.addEventListener('scroll', scheduleScrollMotion, { passive: true })
  window.addEventListener('resize', scheduleScrollMotion)
  reducedMotion.addEventListener?.('change', scheduleScrollMotion)
  sidebarResizeObserver = new ResizeObserver(scheduleScrollMotion)
  sidebarResizeObserver.observe(sidebarElement.value)
  scheduleScrollMotion()
})

onBeforeUnmount(() => {
  clearTimeout(privacyTimer)
  window.cancelAnimationFrame(motionFrame)
  window.removeEventListener('scroll', scheduleScrollMotion)
  window.removeEventListener('resize', scheduleScrollMotion)
  reducedMotion?.removeEventListener?.('change', scheduleScrollMotion)
  sidebarResizeObserver?.disconnect()
})

function maskPhone(value) {
  const phone = String(value || '')
  return phone.length >= 7 ? `${phone.slice(0, 3)}****${phone.slice(-4)}` : (phone || '—')
}

function maskPatientNo(value) {
  const text = String(value || '')
  if (!text) return '—'
  if (text.length <= 6) return `${text.slice(0, 1)}***${text.slice(-1)}`
  return `${text.slice(0, 3)} · · · · · · ${text.slice(-3)}`
}

function togglePrivate() {
  showPrivate.value = !showPrivate.value
  clearTimeout(privacyTimer)
  if (showPrivate.value) privacyTimer = setTimeout(() => { showPrivate.value = false }, 30000)
}

const age = computed(() => calcAge(props.patient.birthDate))
const gender = computed(() => GENDER_MAP[props.patient.gender] || '未知')
const initial = computed(() => (props.patient.name || '?')[0])
const facts = computed(() => [
  { icon: 'phone', label: '手机号', value: showPrivate.value ? (props.patient.phone || '—') : maskPhone(props.patient.phone) },
  { icon: 'idCard', label: '身份证号', value: maskIdCard(props.patient.idCard) },
  { icon: 'calendar', label: '出生日期', value: formatDate(props.patient.birthDate) || '—' },
  { icon: 'mapPin', label: '地址', value: props.patient.address || '—' },
  { icon: 'shield', label: '过敏史', value: props.patient.allergyHistory || '无' },
])
</script>

<template>
  <aside ref="sidebarElement" class="archive-side">
    <section ref="profileCardElement" class="profile-card">
      <div class="profile-cover">
        <div class="profile-cover__label"><UiIcon name="user" :size="15" />个人档案</div>
        <p>您的专属健康空间</p>
      </div>
      <div class="profile-body">
        <label v-if="showSwitcher" class="archive-side__switch">
          当前患者
          <select class="input" :value="activePatientId" @change="setActivePatient($event.target.value)">
            <option v-for="item in patients" :key="item.patientId" :value="item.patientId">
              {{ item.name || '未命名' }}（{{ item.relationType === 'SELF' ? '本人' : item.relationType === 'CHILD' ? '子女' : item.relationType === 'SPOUSE' ? '配偶' : item.relationType === 'PARENT' ? '父母' : '其他' }}）
            </option>
          </select>
        </label>
        <div class="person">
          <span class="avatar" aria-hidden="true">{{ initial }}</span>
          <div>
            <strong>{{ patient.name || '未设置姓名' }}</strong>
            <span>{{ gender }} · {{ age ? `${age} 岁` : '年龄未知' }}</span>
          </div>
        </div>
        <p class="patient-number">患者 ID {{ showPrivate ? (patient.patientNo || '—') : maskPatientNo(patient.patientNo) }}</p>
        <dl class="facts">
          <div v-for="item in facts" :key="item.label">
            <dt><UiIcon :name="item.icon" :size="14" />{{ item.label }}</dt>
            <dd>{{ item.value }}</dd>
          </div>
        </dl>
        <button class="privacy" type="button" :aria-pressed="showPrivate" @click="togglePrivate">
          {{ showPrivate ? '隐藏敏感信息' : '显示完整信息 30 秒' }}
        </button>
        <button class="profile-action" type="button" @click="emit('open-tab', 'basic')">
          修改个人资料 <UiIcon name="arrowRight" :size="14" />
        </button>
      </div>
    </section>

    <section ref="quickCardElement" class="quick-card">
      <h2>快捷操作</h2>
      <div class="quick-list">
        <button type="button" @click="emit('unavailable', '上传健康数据')"><UiIcon name="upload" :size="16" /><span>上传健康数据</span><UiIcon name="arrowRight" :size="14" /></button>
        <button type="button" @click="emit('open-tab', 'documents')"><UiIcon name="record" :size="16" /><span>上传就医资料</span><UiIcon name="arrowRight" :size="14" /></button>
        <button type="button" @click="emit('open-tab', 'history')"><UiIcon name="clipboard" :size="16" /><span>填写健康档案</span><UiIcon name="arrowRight" :size="14" /></button>
        <button type="button" @click="emit('register')"><UiIcon name="calendar" :size="16" /><span>预约挂号</span><UiIcon name="arrowRight" :size="14" /></button>
      </div>
    </section>

    <section class="care-note">
      <UiIcon name="shield" :size="17" />
      <div>
        <strong>您的健康数据已加密保护</strong>
        <p>敏感信息默认隐藏，可短时查看。</p>
      </div>
    </section>
  </aside>
</template>

<style scoped>
.archive-side { position: relative; display: grid; align-content: start; gap: 16px; }
@media (min-width: 821px) {
  .archive-side { position: sticky; top: var(--sidebar-sticky-top, 18px); }
}
.profile-card, .quick-card {
  overflow: hidden;
  border: 1px solid #e0e9e4;
  border-radius: 18px;
  background: #fff;
  box-shadow: 0 10px 30px rgba(35, 80, 68, .04);
  transform: translate3d(0, var(--scroll-y, 0px), 0);
  transform-origin: center;
  will-change: transform;
}
.profile-cover {
  position: relative;
  min-height: 95px;
  padding: 19px 20px;
  overflow: hidden;
  color: #204d42;
  background: #eaf4ed;
}
.profile-cover::before,
.profile-cover::after {
  content: "";
  position: absolute;
  width: 132px;
  height: 132px;
  border: 1px solid rgba(61, 135, 105, .12);
  border-radius: 50%;
}
.profile-cover::before { right: -58px; top: -86px; }
.profile-cover::after { right: 8px; top: -108px; }
.profile-cover__label {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 13px;
  font-weight: 760;
  letter-spacing: .06em;
}
.profile-cover p { position: relative; z-index: 1; margin: 7px 0 0; color: #6c8d7b; font-size: 12px; }
.profile-body { padding: 0 20px 20px; }
.archive-side__switch { display: grid; gap: 6px; margin: 14px 0 0; color: #69847f; font-size: 12px; }
.person { position: relative; display: flex; align-items: center; gap: 12px; margin-top: -15px; }
.avatar {
  display: grid;
  place-items: center;
  width: 54px;
  height: 54px;
  flex: none;
  border: 4px solid #fff;
  border-radius: 16px;
  color: #0a6659;
  background: #d5ede3;
  font-size: 22px;
  font-weight: 760;
  box-shadow: 0 6px 16px rgba(36, 103, 77, .09);
}
.person strong { display: block; color: #1b4038; font-size: 18px; line-height: 1.3; }
.person span { color: #69847f; font-size: 12px; }
.patient-number { margin: 18px 0 9px; color: #82958a; font-size: 11px; letter-spacing: .03em; }
.facts { display: grid; margin: 0; border-top: 1px solid #e8f0ed; }
.facts > div { display: grid; grid-template-columns: 72px minmax(0, 1fr); gap: 6px; align-items: center; padding: 11px 0; border-bottom: 1px solid #edf2ee; }
.facts dt { display: flex; align-items: center; gap: 6px; color: #80948a; font-size: 11px; }
.facts dt :deep(svg) { color: #61a79b; }
.facts dd { margin: 0; color: #25483d; font-size: 11px; font-weight: 700; white-space: nowrap; }
.privacy {
  min-height: 36px;
  margin: 12px 0;
  padding: 0;
  border: 0;
  background: none;
  color: #0b7968;
  font: inherit;
  font-size: 12px;
  font-weight: 750;
  cursor: pointer;
}
.profile-action {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  width: 100%;
  min-height: 42px;
  border: 0;
  border-radius: 10px;
  background: #174f45;
  color: #fff;
  font: inherit;
  font-size: 13px;
  font-weight: 800;
  cursor: pointer;
  transition: background .3s ease, transform .45s cubic-bezier(.22, 1, .36, 1);
}
.profile-action:hover { background: #0d6557; transform: translateY(-1px); }
.quick-card { padding: 18px 16px 9px; }
.quick-card h2 { margin: 0 0 10px 4px; color: #1c433a; font-size: 14px; }
.quick-list button {
  display: grid;
  grid-template-columns: 18px minmax(0, 1fr) 14px;
  align-items: center;
  gap: 10px;
  width: 100%;
  min-height: 46px;
  padding: 0 7px;
  border: 0;
  border-top: 1px solid #f0f5f3;
  background: transparent;
  color: #274740;
  font: inherit;
  font-size: 13px;
  font-weight: 650;
  text-align: left;
  cursor: pointer;
  transition: background .25s ease, color .25s ease;
}
.quick-list button:first-child { border-top: 0; }
.quick-list button:hover { background: #f4fbf9; color: #0b655d; }
.quick-list :deep(svg) { color: #4b998e; }
.care-note {
  display: flex;
  gap: 10px;
  padding: 15px 16px;
  border: 1px solid #e0e9e4;
  border-radius: 14px;
  background: #f1f6f0;
  color: #188f80;
}
.care-note strong { display: block; color: #24695f; font-size: 12px; }
.care-note p { margin: 4px 0 0; color: #77918a; font-size: 12px; line-height: 1.5; }
@media (prefers-reduced-motion: reduce) {
  .profile-card, .quick-card { transform: none; will-change: auto; }
  .profile-action, .quick-list button { transition: none; }
}
</style>
