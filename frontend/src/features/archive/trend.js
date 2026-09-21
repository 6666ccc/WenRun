export const TREND_RANGES = [
  { days: 7, label: '近7天' },
  { days: 30, label: '近30天' },
  { days: 90, label: '近3月' },
  { days: 365, label: '近1年' },
]

export const FALLBACK_METRICS = [
  { metricType: 'WEIGHT', metricName: '体重', unit: 'kg', dualLine: false },
  { metricType: 'BMI', metricName: 'BMI', unit: 'kg/m²', dualLine: false, derived: true },
  { metricType: 'WAIST', metricName: '腰围', unit: 'cm', dualLine: false },
  { metricType: 'BLOOD_PRESSURE', metricName: '血压', unit: 'mmHg', dualLine: true },
  { metricType: 'BLOOD_GLUCOSE', metricName: '血糖', unit: 'mmol/L', dualLine: false },
  { metricType: 'HEART_RATE', metricName: '心率', unit: '次/分', dualLine: false },
  { metricType: 'SPO2', metricName: '血氧', unit: '%', dualLine: false },
  { metricType: 'TEMPERATURE', metricName: '体温', unit: '℃', dualLine: false },
  { metricType: 'RESPIRATORY_RATE', metricName: '呼吸频率', unit: '次/分', dualLine: false },
]

const LINE = '#0f8f82'
const SYS = '#d4535e'
const DIA = '#2aa396'
const AXIS = '#d5e6e6'
const SPLIT = '#eef8f7'
const MUTED = '#7a9194'

export function formatTrendTime(measuredAt) {
  if (!measuredAt) return ''
  const match = String(measuredAt).match(/^(\d{4}-\d{2}-\d{2})/)
  return match ? match[1] : String(measuredAt)
}

export function formatAxisLabel(measuredAt) {
  const date = formatTrendTime(measuredAt)
  return date.length >= 10 ? date.slice(5) : date
}

export function formatMetricNumber(value) {
  const n = Number(value)
  if (!Number.isFinite(n)) return '--'
  return String(Number(n.toFixed(3)))
}

function primaryOf(record) {
  return record?.primaryValue ?? record?.value
}

export function summarizeTrend(metricType, unit, records = []) {
  if (!records.length) {
    return {
      displayValue: '--',
      unit: unit || '',
      changeText: '暂无变化',
      changeKind: 'normal',
      latestTime: '最近记录：--',
    }
  }

  const latest = records[records.length - 1]
  const latestTime = `最近记录：${formatTrendTime(latest.measuredAt) || '--'}`

  if (metricType === 'BLOOD_PRESSURE') {
    return {
      displayValue: `${formatMetricNumber(latest.primaryValue)}/${formatMetricNumber(latest.secondaryValue)}`,
      unit: unit || 'mmHg',
      changeText: '血压趋势',
      changeKind: 'normal',
      latestTime,
    }
  }

  const current = Number(primaryOf(latest))
  let changeText = '暂无变化'
  let changeKind = 'normal'
  if (records.length >= 2) {
    const previous = Number(primaryOf(records[records.length - 2]))
    const diff = current - previous
    if (diff > 0) {
      changeText = `↑ ${Math.abs(diff).toFixed(1)}`
      changeKind = 'up'
    } else if (diff < 0) {
      changeText = `↓ ${Math.abs(diff).toFixed(1)}`
      changeKind = 'down'
    } else {
      changeText = '与上次持平'
    }
  }

  return {
    displayValue: formatMetricNumber(current),
    unit: unit || '',
    changeText,
    changeKind,
    latestTime,
  }
}

function axisStyle() {
  return {
    type: 'category',
    boundaryGap: false,
    axisLine: { lineStyle: { color: AXIS } },
    axisTick: { show: false },
    axisLabel: { color: MUTED },
  }
}

function valueAxis() {
  return {
    type: 'value',
    scale: true,
    splitLine: { lineStyle: { color: SPLIT } },
    axisLabel: { color: MUTED },
  }
}

export function buildChartOption(metricType, metricName, unit, records = []) {
  const xAxis = records.map((item) => formatAxisLabel(item.measuredAt))

  if (metricType === 'BLOOD_PRESSURE') {
    return {
      tooltip: {
        trigger: 'axis',
        formatter(params) {
          const index = params[0]?.dataIndex ?? 0
          const record = records[index] || {}
          return `${formatTrendTime(record.measuredAt)}<br/>收缩压：<b>${formatMetricNumber(record.primaryValue)} ${unit || 'mmHg'}</b><br/>舒张压：<b>${formatMetricNumber(record.secondaryValue)} ${unit || 'mmHg'}</b>`
        },
      },
      legend: { top: 0, data: ['收缩压', '舒张压'] },
      grid: { left: 50, right: 30, top: 50, bottom: 45 },
      xAxis: { ...axisStyle(), data: xAxis },
      yAxis: valueAxis(),
      series: [
        {
          name: '收缩压',
          type: 'line',
          smooth: true,
          data: records.map((item) => Number(item.primaryValue)),
          symbol: 'circle',
          symbolSize: 8,
          lineStyle: { width: 3, color: SYS },
          itemStyle: { color: SYS, borderColor: '#fff', borderWidth: 2 },
        },
        {
          name: '舒张压',
          type: 'line',
          smooth: true,
          data: records.map((item) => Number(item.secondaryValue)),
          symbol: 'circle',
          symbolSize: 8,
          lineStyle: { width: 3, color: DIA },
          itemStyle: { color: DIA, borderColor: '#fff', borderWidth: 2 },
        },
      ],
    }
  }

  const values = records.map((item) => Number(primaryOf(item)))
  return {
    tooltip: {
      trigger: 'axis',
      formatter(params) {
        const index = params[0]?.dataIndex ?? 0
        const record = records[index] || {}
        const value = params[0]?.value
        return `${formatTrendTime(record.measuredAt)}<br/>${metricName}：<b>${formatMetricNumber(value)} ${unit || ''}</b>`
      },
    },
    grid: { left: 50, right: 30, top: 45, bottom: 45 },
    xAxis: { ...axisStyle(), data: xAxis },
    yAxis: valueAxis(),
    series: [
      {
        name: metricName,
        type: 'line',
        smooth: true,
        data: values,
        symbol: 'circle',
        symbolSize: 8,
        lineStyle: { width: 3, color: LINE },
        itemStyle: { color: LINE, borderColor: '#fff', borderWidth: 2 },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(15,143,130,0.20)' },
              { offset: 1, color: 'rgba(15,143,130,0.01)' },
            ],
          },
        },
      },
    ],
  }
}
