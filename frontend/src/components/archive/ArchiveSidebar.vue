<script setup>
import { computed, onBeforeUnmount, ref } from 'vue'
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
let privacyTimer

function maskPhone(value) {
  const phone = String(value || '')
  return phone.length >= 7 ? `${phone.slice(0, 3)}****${phone.slice(-4)}` : (phone || '—')
}

function maskPatientNo(value) {
  const text = String(value || '')
  if (!text) return '—'
  if (text.length <= 6) return `${text.slice(0, 1)}***${text.slice(-1)}`
  return `${text.slice(0, 3)}••••••${text.slice(-3)}`
}

function togglePrivate() {
  showPrivate.value = !showPrivate.value
  clearTimeout(privacyTimer)
  if (showPrivate.value) privacyTimer = setTimeout(() => { showPrivate.value = false }, 30000)
}

onBeforeUnmount(() => clearTimeout(privacyTimer))

const age = computed(() => calcAge(props.patient.birthDate))
const gender = computed(() => GENDER_MAP[props.patient.gender] || '未知')
const initial = computed(() => (props.patient.name || '?')[0])
const facts = computed(() => [
  { icon: 'phone', label: '手机号', value: showPrivate.value ? (props.patient.phone || '—') : maskPhone(props.patient.phone) },
  { icon: 'idCard', label: '身份证号', value: maskIdCard(props.patient.idCard) },
  { icon: 'calendar', label: '出生日期', value: formatDate(props.patient.birthDate) || '—' },
  { icon: 'mapPin', label: '地址', value: props.patient.address || '—' },
  { icon: 'alert', label: '过敏史', value: props.patient.allergyHistory || '无' },
])
</script>

<template>
  <aside class="archive-side">
    <RouterLink class="archive-side__home" to="/home">‹ 返回首页</RouterLink>
    <section class="archive-side__card">
      <h1>个人档案</h1>
      <label v-if="showSwitcher" class="archive-side__switch">
        当前患者
        <select class="input" :value="activePatientId" @change="setActivePatient($event.target.value)">
          <option v-for="item in patients" :key="item.patientId" :value="item.patientId">
            {{ item.name || '未命名' }}（{{ item.relationType === 'SELF' ? '本人' : item.relationType === 'CHILD' ? '子女' : item.relationType === 'SPOUSE' ? '配偶' : item.relationType === 'PARENT' ? '父母' : '其他' }}）
          </option>
        </select>
      </label>
      <div class="archive-side__hero">
        <span class="archive-side__avatar" aria-hidden="true">{{ initial }}</span>
        <div>
          <strong>{{ patient.name || '未设置姓名' }}</strong>
          <p>{{ gender }} · {{ age ? `${age}岁` : '年龄未知' }}</p>
          <small>患者ID {{ showPrivate ? (patient.patientNo || '—') : maskPatientNo(patient.patientNo) }}</small>
        </div>
      </div>
      <dl class="archive-side__facts">
        <div v-for="item in facts" :key="item.label">
          <dt><UiIcon :name="item.icon" :size="15" />{{ item.label }}</dt>
          <dd>{{ item.value }}</dd>
        </div>
      </dl>
      <button class="archive-side__privacy" type="button" :aria-pressed="showPrivate" @click="togglePrivate">
        {{ showPrivate ? '隐藏敏感信息' : '显示完整信息 30 秒' }}
      </button>
      <button class="archive-side__more" type="button" @click="emit('open-tab', 'basic')">修改资料 →</button>
    </section>

    <section class="archive-side__card">
      <h2>快捷操作</h2>
      <div class="archive-side__actions">
        <button type="button" @click="emit('unavailable', '上传健康数据')"><UiIcon name="upload" :size="16" /><span>上传健康数据</span><UiIcon name="arrowRight" :size="14" /></button>
        <button type="button" @click="emit('open-tab', 'documents')"><UiIcon name="record" :size="16" /><span>上传就医资料</span><UiIcon name="arrowRight" :size="14" /></button>
        <button type="button" @click="emit('open-tab', 'history')"><UiIcon name="clipboard" :size="16" /><span>填写健康档案</span><UiIcon name="arrowRight" :size="14" /></button>
        <button type="button" @click="emit('register')"><UiIcon name="calendar" :size="16" /><span>预约挂号</span><UiIcon name="arrowRight" :size="14" /></button>
      </div>
    </section>

    <section class="archive-side__note">
      <UiIcon name="shield" :size="18" />
      <div>
        <strong>您的健康数据已加密保护</strong>
        <p>我们严格遵守医疗数据安全规范</p>
      </div>
    </section>
  </aside>
</template>

<style scoped>
.archive-side { display: grid; align-content: start; gap: 16px; }
.archive-side__home {
  justify-self: start;
  color: var(--color-brand-800);
  font-size: 13px;
  font-weight: 700;
  text-decoration: none;
}
.archive-side__card, .archive-side__note {
  border: 1px solid var(--color-border);
  border-radius: 20px;
  background: #fff;
}
.archive-side__card { padding: 20px 18px 16px; }
.archive-side__card h1, .archive-side__card h2 { margin: 0 0 16px; font-size: 15px; color: var(--color-text); }
.archive-side__switch { display: grid; gap: 6px; margin: 0 0 14px; color: var(--color-text-secondary); font-size: 12px; }
.archive-side__hero { display: flex; gap: 12px; align-items: center; margin-bottom: 18px; }
.archive-side__avatar {
  width: 56px; height: 56px; display: grid; place-items: center; flex: 0 0 56px;
  border-radius: 50%; background: var(--color-mint-100); color: var(--color-brand-800); font-size: 22px; font-weight: 700;
}
.archive-side__hero strong { display: block; font-size: 18px; }
.archive-side__hero p, .archive-side__hero small { margin: 4px 0 0; color: var(--color-text-secondary); font-size: 13px; }
.archive-side__facts { display: grid; gap: 10px; margin: 0; }
.archive-side__facts > div { display: grid; grid-template-columns: 92px minmax(0, 1fr); gap: 8px; align-items: start; }
.archive-side__facts dt { display: flex; align-items: center; gap: 6px; color: var(--color-text-muted); font-size: 12px; font-weight: 600; }
.archive-side__facts dd { margin: 0; color: var(--color-text); font-size: 13px; word-break: break-all; }
.archive-side__more {
  width: 100%; margin-top: 16px; padding: 10px 0; border: 0; border-radius: 12px;
  background: var(--color-mint-050); color: var(--color-brand-800); font: inherit; font-weight: 700; cursor: pointer;
}
.archive-side__privacy {
  min-height: 44px; margin-top: 12px; padding: 0 8px; border: 0; border-radius: 10px;
  background: transparent; color: var(--color-brand-700); font: inherit; font-size: 12px; font-weight: 700; cursor: pointer;
}
.archive-side__privacy:hover, .archive-side__privacy:focus-visible { background: var(--color-mint-050); }
.archive-side__actions { display: grid; gap: 6px; }
.archive-side__actions button {
  display: grid; grid-template-columns: 18px minmax(0, 1fr) 14px; align-items: center; gap: 10px;
  min-height: 44px; padding: 0 8px; border: 0; border-radius: 12px; background: transparent;
  color: var(--color-text); font: inherit; text-align: left; cursor: pointer;
}
.archive-side__actions button:hover, .archive-side__more:hover { background: var(--color-mint-100); }
.archive-side__note {
  display: flex; gap: 10px; align-items: flex-start; padding: 14px 16px;
  background: var(--color-info-bg);
  color: var(--color-info);
}
.archive-side__note p { margin: 4px 0 0; font-size: 12px; color: var(--color-text-secondary); }
</style>
