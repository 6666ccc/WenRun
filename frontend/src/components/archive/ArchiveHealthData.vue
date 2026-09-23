<script setup>
import { computed, defineAsyncComponent } from 'vue'
import { formatDate, formatDateTime, GENDER_MAP } from '../../utils'
import { maskIdCard } from '../../features/archive/tabs'
import { calcBmi, calcWhtr, formatBloodPressure, formatGlucoseType } from '../../utils/healthProfile'
import ArchiveTrendSkeleton from './ArchiveTrendSkeleton.vue'
import UiIcon from '../UiIcon.vue'

const props = defineProps({
  patient: { type: Object, default: null },
  health: { type: Object, default: null },
  patientId: { type: [String, Number], default: null },
  error: { type: String, default: '' },
})
const emit = defineEmits(['record', 'unavailable', 'open-tab'])
const ArchiveHealthTrend = defineAsyncComponent({
  loader: () => import('./ArchiveHealthTrend.vue'),
  loadingComponent: ArchiveTrendSkeleton,
  delay: 80,
})

const bmi = computed(() => calcBmi(props.health?.heightCm, props.health?.weightKg))
const whtr = computed(() => props.health?.whtr ?? calcWhtr(props.health?.heightCm, props.health?.waistCm))
const pressure = computed(() => formatBloodPressure(props.health?.systolicMmhg, props.health?.diastolicMmhg))
const glucose = computed(() => {
  if (props.health?.glucoseMmol == null || props.health?.glucoseMmol === '') return ''
  return `${props.health.glucoseMmol} ${formatGlucoseType(props.health.glucoseType)}`.trim()
})
const updatedAt = computed(() => formatDateTime(props.health?.measuredAt) || '—')
const histories = computed(() => [
  { key: 'pastHistory', label: '既往史', desc: '既往疾病、手术、过敏、疫苗接种', value: props.health?.pastHistory },
  { key: 'familyHistory', label: '家族史', desc: '家族患病情况', value: props.health?.familyHistory },
  { key: 'personalHistory', label: '个人史', desc: '吸烟、饮酒情况', value: props.health?.personalHistory },
])

const basics = computed(() => [
  { label: '姓名', value: props.patient?.name || '—' },
  { label: '性别', value: GENDER_MAP[props.patient?.gender] || '未知' },
  { label: '手机号', value: props.patient?.phone || '—' },
  { label: '身份证号', value: maskIdCard(props.patient?.idCard) },
  { label: '出生日期', value: formatDate(props.patient?.birthDate) || '—' },
  { label: '过敏史', value: props.patient?.allergyHistory || '无' },
])
</script>

<template>
  <div class="health-data">
    <p v-if="error" class="archive-panel__error" role="alert">{{ error }}</p>

    <section class="archive-panel">
      <header>
        <div>
          <h2>体型数据</h2>
          <p>最近更新：{{ updatedAt }}</p>
        </div>
      </header>
      <div class="metric-grid">
        <article class="metric-card">
          <span class="metric-card__icon is-blue"><UiIcon name="weight" :size="18" /></span>
          <div>
            <small>体重</small>
            <strong>{{ health?.weightKg ?? '--' }} <em>kg</em></strong>
          </div>
          <button type="button" aria-label="记录体重" @click="emit('record', 'weight')"><UiIcon name="plus" :size="16" /></button>
        </article>
        <article class="metric-card">
          <span class="metric-card__icon is-violet"><UiIcon name="ruler" :size="18" /></span>
          <div>
            <small>腰围</small>
            <strong>{{ health?.waistCm ?? '--' }} <em>cm</em></strong>
          </div>
          <button type="button" aria-label="记录腰围" @click="emit('record', 'waist')"><UiIcon name="plus" :size="16" /></button>
        </article>
        <article class="metric-card">
          <span class="metric-card__icon is-amber"><UiIcon name="ruler" :size="18" /></span>
          <div>
            <small>身高</small>
            <strong>{{ health?.heightCm ?? '--' }} <em>cm</em></strong>
          </div>
          <button type="button" aria-label="记录身高" @click="emit('record', 'height')"><UiIcon name="plus" :size="16" /></button>
        </article>
        <article class="metric-card metric-card--wide">
          <small>BMI <UiIcon name="info" :size="13" /></small>
          <strong>{{ bmi || '--' }}</strong>
        </article>
        <article class="metric-card metric-card--wide">
          <small>WHtR <UiIcon name="info" :size="13" /></small>
          <strong>{{ whtr || '--' }}</strong>
        </article>
      </div>
    </section>

    <section class="archive-panel">
      <header>
        <div>
          <h2>生命体征</h2>
          <p>最近更新：{{ updatedAt }}</p>
        </div>
      </header>
      <div class="vital-grid">
        <article class="metric-card">
          <span class="metric-card__icon is-rose"><UiIcon name="heart" :size="18" /></span>
          <div>
            <small>血压</small>
            <strong>{{ pressure || '--' }} <em>mmHg</em></strong>
          </div>
          <button type="button" aria-label="记录血压" @click="emit('record', 'bp')"><UiIcon name="plus" :size="16" /></button>
        </article>
        <article class="metric-card">
          <span class="metric-card__icon is-red"><UiIcon name="droplet" :size="18" /></span>
          <div>
            <small>血糖</small>
            <strong>{{ glucose || '--' }} <em>mmol/L</em></strong>
          </div>
          <button type="button" aria-label="记录血糖" @click="emit('record', 'glucose')"><UiIcon name="plus" :size="16" /></button>
        </article>
        <article class="metric-card">
          <span class="metric-card__icon is-pink"><UiIcon name="activity" :size="18" /></span>
          <div>
            <small>心率</small>
            <strong>{{ health?.heartRateBpm ?? '--' }} <em>次/分</em></strong>
          </div>
          <button type="button" aria-label="记录心率" @click="emit('record', 'hr')"><UiIcon name="plus" :size="16" /></button>
        </article>
        <article class="metric-card">
          <span class="metric-card__icon is-sky"><UiIcon name="wind" :size="18" /></span>
          <div>
            <small>血氧</small>
            <strong>{{ health?.spo2Pct ?? '--' }} <em>%</em></strong>
          </div>
          <button type="button" aria-label="记录血氧" @click="emit('record', 'spo2')"><UiIcon name="plus" :size="16" /></button>
        </article>
        <article class="metric-card">
          <span class="metric-card__icon is-blue"><UiIcon name="activity" :size="18" /></span>
          <div>
            <small>呼吸</small>
            <strong>{{ health?.respiratoryRateBpm ?? '--' }} <em>次/分</em></strong>
          </div>
          <button type="button" aria-label="记录呼吸" @click="emit('record', 'rr')"><UiIcon name="plus" :size="16" /></button>
        </article>
        <article class="metric-card">
          <span class="metric-card__icon is-amber"><UiIcon name="thermometer" :size="18" /></span>
          <div>
            <small>体温</small>
            <strong>{{ health?.temperatureC ?? '--' }} <em>°C</em></strong>
          </div>
          <button type="button" aria-label="记录体温" @click="emit('record', 'temp')"><UiIcon name="plus" :size="16" /></button>
        </article>
      </div>
    </section>

    <section class="archive-panel">
      <header>
        <h2>健康信息</h2>
        <button class="archive-link" type="button" @click="emit('open-tab', 'history')">完善信息 ›</button>
      </header>
      <div class="history-list">
        <button v-for="item in histories" :key="item.key" type="button" @click="emit('open-tab', 'history')">
          <span :class="['metric-card__icon', item.key === 'familyHistory' ? 'is-green' : item.key === 'personalHistory' ? 'is-violet' : 'is-blue']">
            <UiIcon :name="item.key === 'familyHistory' ? 'users' : item.key === 'personalHistory' ? 'user' : 'clipboard'" :size="16" />
          </span>
          <span>
            <strong>{{ item.label }}</strong>
            <small>{{ item.value || item.desc }}</small>
          </span>
        </button>
      </div>
    </section>

    <ArchiveHealthTrend
      :patient-id="patientId"
      :refresh-key="`${patientId}:${health?.updateTime || health?.measuredAt || ''}`"
    />
  </div>
</template>
