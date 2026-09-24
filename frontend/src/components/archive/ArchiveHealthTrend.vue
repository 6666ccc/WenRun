<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import * as echarts from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { getHealthMetricTrend, listHealthMetricTypes } from '../../api'
import { FALLBACK_METRICS, TREND_RANGES, buildChartOption, summarizeTrend } from '../../features/archive/trend'

echarts.use([LineChart, GridComponent, LegendComponent, TooltipComponent, CanvasRenderer])

const props = defineProps({
  patientId: { type: [String, Number], default: null },
  refreshKey: { type: [String, Number], default: '' },
})
const metricType = ref('WEIGHT')
const range = ref(30)
const types = ref(FALLBACK_METRICS)
const trend = ref(null)
const loading = ref(false)
const error = ref('')
const chartEl = ref(null)

let chart
let resizeObs

const records = computed(() => trend.value?.records || [])
const currentType = computed(() => types.value.find((item) => item.metricType === metricType.value) || types.value[0])
const unit = computed(() => trend.value?.unit || currentType.value?.unit || '')
const summary = computed(() => summarizeTrend(metricType.value, unit.value, records.value))
const hasChart = computed(() => !loading.value && !error.value && records.value.length > 0)

async function loadTypes() {
  try {
    const data = await listHealthMetricTypes()
    if (Array.isArray(data) && data.length) types.value = data
  } catch {
    types.value = FALLBACK_METRICS
  }
}

async function loadTrend() {
  if (!props.patientId) {
    trend.value = { records: [] }
    error.value = ''
    return
  }
  loading.value = true
  error.value = ''
  try {
    trend.value = await getHealthMetricTrend(props.patientId, metricType.value, range.value)
  } catch (nextError) {
    trend.value = { records: [] }
    error.value = nextError.message || '趋势加载失败'
  } finally {
    loading.value = false
  }
}

function renderChart() {
  if (!chartEl.value || !hasChart.value) {
    chart?.clear()
    return
  }
  if (!chart) chart = echarts.init(chartEl.value)
  chart.setOption(buildChartOption(
    metricType.value,
    trend.value?.metricName || currentType.value?.metricName || '',
    unit.value,
    records.value,
  ), true)
  chart.resize()
}

function onResize() {
  chart?.resize()
}

watch([metricType, range, () => props.patientId], loadTrend, { immediate: true })
watch(() => props.refreshKey, (next, prev) => {
  if (prev !== undefined && next !== prev) loadTrend()
})
watch([hasChart, records, metricType], () => nextTick(renderChart))

onMounted(async () => {
  await loadTypes()
  await nextTick()
  renderChart()
  if (chartEl.value && typeof ResizeObserver !== 'undefined') {
    resizeObs = new ResizeObserver(onResize)
    resizeObs.observe(chartEl.value)
  }
  window.addEventListener('resize', onResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', onResize)
  resizeObs?.disconnect()
  chart?.dispose()
  chart = null
})
</script>

<template>
  <section class="archive-panel">
    <header>
      <div>
        <h2>健康趋势</h2>
        <p>持续记录，了解身体变化趋势</p>
      </div>
      <div class="trend-controls">
        <label class="sr-only" for="metric-select">健康指标</label>
        <select id="metric-select" v-model="metricType" class="metric-select">
          <option v-for="item in types" :key="item.metricType" :value="item.metricType">
            {{ item.metricName }}
          </option>
        </select>
        <div class="range-group" role="group" aria-label="趋势时间范围">
          <button
            v-for="item in TREND_RANGES"
            :key="item.days"
            type="button"
            class="range-btn"
            :class="{ active: range === item.days }"
            @click="range = item.days"
          >{{ item.label }}</button>
        </div>
      </div>
    </header>

    <div class="trend-summary">
      <div class="trend-summary__main">
        <span class="trend-summary__value">{{ summary.displayValue }}</span>
        <span class="trend-summary__unit">{{ summary.unit }}</span>
      </div>
      <span class="trend-change" :class="summary.changeKind">{{ summary.changeText }}</span>
      <span class="trend-summary__time">{{ summary.latestTime }}</span>
    </div>

    <p v-if="loading" class="trend-status">趋势加载中…</p>
    <p v-else-if="error" class="archive-panel__error" role="alert">{{ error }}</p>
    <div v-show="hasChart" ref="chartEl" class="trend-chart" role="img" :aria-label="`${currentType?.metricName || '健康'}趋势图`" />
    <div v-if="!loading && !error && !records.length" class="trend-empty">
      <strong>暂无健康趋势数据</strong>
      <span>记录健康指标后，将在这里生成趋势图</span>
    </div>
  </section>
</template>

<style scoped>
.archive-panel header > div:first-child { position: relative; display: block; padding-left: 14px; }
.archive-panel header > div:first-child::before { position: absolute; top: 0; left: 0; margin: 0; }
.trend-controls {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
  flex-wrap: wrap;
}
.metric-select {
  height: 38px;
  padding: 0 34px 0 14px;
  border: 1px solid var(--color-border);
  border-radius: 9px;
  background: #fff;
  color: var(--color-text);
  font: inherit;
  font-size: 14px;
  outline: none;
  cursor: pointer;
}
.metric-select:focus {
  border-color: var(--color-focus);
}
.range-group {
  display: flex;
  padding: 4px;
  background: var(--color-surface-soft);
  border-radius: 9px;
}
.range-btn {
  border: 0;
  background: transparent;
  padding: 7px 13px;
  border-radius: 7px;
  color: var(--color-text-secondary);
  font: inherit;
  font-size: 13px;
  cursor: pointer;
}
.range-btn:hover { color: var(--color-brand-800); }
.range-btn.active {
  background: #fff;
  color: var(--color-brand-800);
  box-shadow: 0 2px 8px rgba(7, 91, 85, .08);
  font-weight: 700;
}
.trend-summary {
  display: flex;
  align-items: flex-end;
  gap: 18px;
  margin: 4px 0 8px;
}
.trend-summary__main {
  display: flex;
  align-items: flex-end;
  gap: 8px;
}
.trend-summary__value {
  font-size: 32px;
  line-height: 1;
  font-weight: 750;
  color: var(--color-text);
}
.trend-summary__unit {
  margin-bottom: 3px;
  font-size: 14px;
  color: var(--color-text-secondary);
}
.trend-change {
  margin-bottom: 2px;
  padding: 5px 10px;
  border-radius: 20px;
  font-size: 13px;
  font-weight: 700;
}
.trend-change.down { color: var(--color-success); background: var(--color-success-bg); }
.trend-change.up { color: var(--color-danger); background: var(--color-danger-bg); }
.trend-change.normal { color: var(--color-text-secondary); background: var(--color-surface-soft); }
.trend-summary__time {
  margin-left: auto;
  margin-bottom: 3px;
  font-size: 13px;
  color: var(--color-text-muted);
}
.trend-chart { width: 100%; height: 380px; }
.trend-status { margin: 0; color: var(--color-text-secondary); font-size: 13px; }
.trend-empty {
  height: 280px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  color: var(--color-text-muted);
}
.trend-empty strong { font-size: 16px; color: var(--color-text-secondary); font-weight: 650; }
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
@media (max-width: 768px) {
  .archive-panel header { flex-direction: column; align-items: stretch; }
  .trend-controls { display: grid; grid-template-columns: minmax(0, 1fr); justify-content: stretch; }
  .metric-select { width: 100%; }
  .range-group { width: 100%; }
  .range-btn { flex: 1; min-width: 0; padding: 8px 2px; white-space: nowrap; }
  .trend-summary { flex-wrap: wrap; }
  .trend-summary__time { width: 100%; margin-left: 0; }
  .trend-chart { height: 280px; }
}
</style>
