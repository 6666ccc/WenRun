<script setup>
import { computed } from 'vue'
import { formatDateTime } from '../../utils'
import { calcBmi, calcWhtr, formatBloodPressure, formatGlucoseType } from '../../utils/healthProfile'
import UiIcon from '../UiIcon.vue'

const props = defineProps({
  health: { type: Object, default: null },
  error: { type: String, default: '' },
})
const emit = defineEmits(['record', 'unavailable', 'open-tab'])

const bmi = computed(() => calcBmi(props.health?.heightCm, props.health?.weightKg))
const whtr = computed(() => calcWhtr(props.health?.heightCm, props.health?.waistCm))
const pressure = computed(() => formatBloodPressure(props.health?.systolicMmhg, props.health?.diastolicMmhg))
const glucoseNote = computed(() => formatGlucoseType(props.health?.glucoseType))
const updatedAt = computed(() => formatDateTime(props.health?.measuredAt) || '—')
const histories = computed(() => [
  { key: 'pastHistory', label: '既往史', desc: '既往疾病、手术、过敏、疫苗接种', value: props.health?.pastHistory },
  { key: 'familyHistory', label: '家族史', desc: '家族患病情况', value: props.health?.familyHistory },
  { key: 'personalHistory', label: '个人史', desc: '吸烟、饮酒情况', value: props.health?.personalHistory },
])

</script>

<template>
  <div class="health-data">
    <p v-if="error" class="archive-panel__error" role="alert">{{ error }}</p>

    <div class="archive-panel health-data__panel">
      <section class="health-data__group" aria-labelledby="archive-body-title">
      <header>
        <div>
          <div>
            <h2 id="archive-body-title">身体数据</h2>
            <p>最近记录 · {{ updatedAt }}</p>
          </div>
        </div>
        <span class="archive-section__index">01 / BODY</span>
      </header>
      <div class="metric-grid">
        <article class="metric-card">
          <div class="metric-card__head">
            <span class="metric-card__icon"><UiIcon name="weight" :size="16" /></span>
            <span class="metric-card__label">体重</span>
            <button type="button" aria-label="记录体重" @click="emit('record', 'weight')"><UiIcon name="plus" :size="14" /></button>
          </div>
          <strong>{{ health?.weightKg ?? '—' }}<small>kg</small></strong>
          <span class="metric-card__foot">最近一次记录</span>
        </article>
        <article class="metric-card">
          <div class="metric-card__head">
            <span class="metric-card__icon"><UiIcon name="ruler" :size="16" /></span>
            <span class="metric-card__label">身高</span>
            <button type="button" aria-label="记录身高" @click="emit('record', 'height')"><UiIcon name="plus" :size="14" /></button>
          </div>
          <strong>{{ health?.heightCm ?? '—' }}<small>cm</small></strong>
          <span class="metric-card__foot">最近一次记录</span>
        </article>
        <article class="metric-card metric-card--featured">
          <div class="metric-card__head">
            <span class="metric-card__icon"><UiIcon name="activity" :size="16" /></span>
            <span class="metric-card__label">BMI · 身体质量指数</span>
          </div>
          <strong>{{ bmi || '—' }}</strong>
          <span class="metric-card__foot">根据身高与体重计算</span>
        </article>
      </div>
      <div class="metric-grid metric-grid--quiet">
        <article class="metric-card">
          <div class="metric-card__head">
            <span class="metric-card__icon"><UiIcon name="ruler" :size="16" /></span>
            <span class="metric-card__label">腰围</span>
            <button type="button" aria-label="记录腰围" @click="emit('record', 'waist')"><UiIcon name="plus" :size="14" /></button>
          </div>
          <strong>{{ health?.waistCm ?? '—' }}<small>cm</small></strong>
          <span class="metric-card__foot">最近一次记录</span>
        </article>
        <article class="metric-card">
          <div class="metric-card__head">
            <span class="metric-card__icon"><UiIcon name="activity" :size="16" /></span>
            <span class="metric-card__label">腰高比 WHtR</span>
          </div>
          <strong>{{ whtr || '—' }}</strong>
          <span class="metric-card__foot">根据腰围与身高计算</span>
        </article>
      </div>
      </section>

      <section class="health-data__group" aria-labelledby="archive-vitals-title">
      <header>
        <div>
          <div>
            <h2 id="archive-vitals-title">生命体征</h2>
            <p>最近记录 · {{ updatedAt }}</p>
          </div>
        </div>
        <span class="archive-section__index">02 / VITALS</span>
      </header>
      <div class="vital-grid">
        <article class="metric-card">
          <div class="metric-card__head">
            <span class="metric-card__icon"><UiIcon name="heart" :size="16" /></span>
            <span class="metric-card__label">血压</span>
            <button type="button" aria-label="记录血压" @click="emit('record', 'bp')"><UiIcon name="plus" :size="14" /></button>
          </div>
          <strong>{{ pressure || '—' }}<small>mmHg</small></strong>
        </article>
        <article class="metric-card">
          <div class="metric-card__head">
            <span class="metric-card__icon"><UiIcon name="droplet" :size="16" /></span>
            <span class="metric-card__label">血糖</span>
            <button type="button" aria-label="记录血糖" @click="emit('record', 'glucose')"><UiIcon name="plus" :size="14" /></button>
          </div>
          <strong>{{ health?.glucoseMmol ?? '—' }}<small>mmol/L</small></strong>
          <span v-if="glucoseNote" class="metric-card__foot">{{ glucoseNote }}</span>
        </article>
        <article class="metric-card">
          <div class="metric-card__head">
            <span class="metric-card__icon"><UiIcon name="activity" :size="16" /></span>
            <span class="metric-card__label">心率</span>
            <button type="button" aria-label="记录心率" @click="emit('record', 'hr')"><UiIcon name="plus" :size="14" /></button>
          </div>
          <strong>{{ health?.heartRateBpm ?? '—' }}<small>次/分</small></strong>
        </article>
        <article class="metric-card">
          <div class="metric-card__head">
            <span class="metric-card__icon"><UiIcon name="wind" :size="16" /></span>
            <span class="metric-card__label">血氧</span>
            <button type="button" aria-label="记录血氧" @click="emit('record', 'spo2')"><UiIcon name="plus" :size="14" /></button>
          </div>
          <strong>{{ health?.spo2Pct ?? '—' }}<small>%</small></strong>
        </article>
        <article class="metric-card">
          <div class="metric-card__head">
            <span class="metric-card__icon"><UiIcon name="activity" :size="16" /></span>
            <span class="metric-card__label">呼吸</span>
            <button type="button" aria-label="记录呼吸" @click="emit('record', 'rr')"><UiIcon name="plus" :size="14" /></button>
          </div>
          <strong>{{ health?.respiratoryRateBpm ?? '—' }}<small>次/分</small></strong>
        </article>
        <article class="metric-card">
          <div class="metric-card__head">
            <span class="metric-card__icon"><UiIcon name="thermometer" :size="16" /></span>
            <span class="metric-card__label">体温</span>
            <button type="button" aria-label="记录体温" @click="emit('record', 'temp')"><UiIcon name="plus" :size="14" /></button>
          </div>
          <strong>{{ health?.temperatureC ?? '—' }}<small>°C</small></strong>
        </article>
      </div>
      </section>

      <section class="health-data__group" aria-labelledby="archive-history-title">
      <header>
        <div>
          <div>
            <h2 id="archive-history-title">健康信息</h2>
            <p>重要病史与生活习惯</p>
          </div>
        </div>
        <button class="archive-link" type="button" @click="emit('open-tab', 'history')">完善信息 <UiIcon name="arrowRight" :size="14" /></button>
      </header>
      <div class="history-list">
        <button v-for="item in histories" :key="item.key" type="button" @click="emit('open-tab', 'history')">
          <span class="metric-card__icon">
            <UiIcon :name="item.key === 'familyHistory' ? 'users' : item.key === 'personalHistory' ? 'user' : 'clipboard'" :size="16" />
          </span>
          <span>
            <strong>{{ item.label }}</strong>
            <small>{{ item.value || item.desc }}</small>
          </span>
        </button>
      </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.health-data__panel { padding: 0 28px; }
.health-data__group { padding: 27px 0 29px; }
.health-data__group + .health-data__group { border-top: 1px solid #e6eeea; }
@media (max-width: 767px) {
  .health-data__panel { padding: 0 16px; }
  .health-data__group { padding: 22px 0 24px; }
}
</style>
