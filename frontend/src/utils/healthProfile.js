/** 血糖类型 */
export const GLUCOSE_TYPE_MAP = {
  fasting: '空腹',
  random: '随机',
  postprandial: '餐后',
}

export function formatGlucoseType(type) {
  if (!type) return ''
  return GLUCOSE_TYPE_MAP[type] || type
}

export function formatBloodPressure(systolic, diastolic) {
  if (systolic == null && diastolic == null) return ''
  if (systolic == null || diastolic == null) return `${systolic ?? '—'} / ${diastolic ?? '—'}`
  return `${systolic} / ${diastolic}`
}

export function calcBmi(heightCm, weightKg) {
  const height = Number(heightCm)
  const weight = Number(weightKg)
  if (!Number.isFinite(height) || !Number.isFinite(weight) || height <= 0 || weight <= 0) return ''
  const bmi = weight / ((height / 100) ** 2)
  return bmi.toFixed(1)
}

export function toDatetimeLocal(value) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    const match = String(value).match(/^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2})/)
    return match ? `${match[1]}T${match[2]}` : ''
  }
  const pad = (n) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}

export function emptyHealthForm() {
  return {
    heightCm: '',
    weightKg: '',
    systolicMmhg: '',
    diastolicMmhg: '',
    glucoseMmol: '',
    glucoseType: '',
    heartRateBpm: '',
    spo2Pct: '',
    respiratoryRateBpm: '',
    temperatureC: '',
    measuredAt: '',
    pastHistory: '',
    familyHistory: '',
    personalHistory: '',
  }
}

function toOptionalNumber(value) {
  if (value === '' || value == null) return null
  const next = Number(value)
  return Number.isFinite(next) ? next : null
}

export function toHealthPayload(form) {
  return {
    heightCm: toOptionalNumber(form.heightCm),
    weightKg: toOptionalNumber(form.weightKg),
    systolicMmhg: toOptionalNumber(form.systolicMmhg),
    diastolicMmhg: toOptionalNumber(form.diastolicMmhg),
    glucoseMmol: toOptionalNumber(form.glucoseMmol),
    glucoseType: form.glucoseType || null,
    heartRateBpm: toOptionalNumber(form.heartRateBpm),
    spo2Pct: toOptionalNumber(form.spo2Pct),
    respiratoryRateBpm: toOptionalNumber(form.respiratoryRateBpm),
    temperatureC: toOptionalNumber(form.temperatureC),
    measuredAt: form.measuredAt || null,
    pastHistory: form.pastHistory?.trim() || null,
    familyHistory: form.familyHistory?.trim() || null,
    personalHistory: form.personalHistory?.trim() || null,
  }
}

export function fillHealthForm(data = {}) {
  return {
    heightCm: data.heightCm ?? '',
    weightKg: data.weightKg ?? '',
    systolicMmhg: data.systolicMmhg ?? '',
    diastolicMmhg: data.diastolicMmhg ?? '',
    glucoseMmol: data.glucoseMmol ?? '',
    glucoseType: data.glucoseType || '',
    heartRateBpm: data.heartRateBpm ?? '',
    spo2Pct: data.spo2Pct ?? '',
    respiratoryRateBpm: data.respiratoryRateBpm ?? '',
    temperatureC: data.temperatureC ?? '',
    measuredAt: toDatetimeLocal(data.measuredAt),
    pastHistory: data.pastHistory || '',
    familyHistory: data.familyHistory || '',
    personalHistory: data.personalHistory || '',
  }
}

export const METRIC_EDITORS = {
  weight: {
    title: '记录体重',
    fields: [{ key: 'weightKg', label: '体重 kg', type: 'number', step: '0.1', min: 10, max: 300 }],
  },
  height: {
    title: '记录身高',
    fields: [{ key: 'heightCm', label: '身高 cm', type: 'number', step: '0.1', min: 50, max: 250 }],
  },
  bp: {
    title: '记录血压',
    fields: [
      { key: 'systolicMmhg', label: '收缩压 mmHg', type: 'number', min: 60, max: 250 },
      { key: 'diastolicMmhg', label: '舒张压 mmHg', type: 'number', min: 40, max: 180 },
    ],
  },
  glucose: {
    title: '记录血糖',
    fields: [
      { key: 'glucoseMmol', label: '血糖 mmol/L', type: 'number', step: '0.1', min: 1, max: 40 },
      {
        key: 'glucoseType',
        label: '血糖类型',
        type: 'select',
        options: [
          { value: '', label: '未填写' },
          { value: 'fasting', label: '空腹' },
          { value: 'random', label: '随机' },
          { value: 'postprandial', label: '餐后' },
        ],
      },
    ],
  },
  hr: {
    title: '记录心率',
    fields: [{ key: 'heartRateBpm', label: '心率 次/分', type: 'number', min: 30, max: 220 }],
  },
  spo2: {
    title: '记录血氧',
    fields: [{ key: 'spo2Pct', label: '血氧 %', type: 'number', min: 50, max: 100 }],
  },
  rr: {
    title: '记录呼吸',
    fields: [{ key: 'respiratoryRateBpm', label: '呼吸 次/分', type: 'number', min: 8, max: 40 }],
  },
  temp: {
    title: '记录体温',
    fields: [{ key: 'temperatureC', label: '体温 ℃', type: 'number', step: '0.1', min: 35, max: 42 }],
  },
}

export function metricEditor(id) {
  return METRIC_EDITORS[id] || null
}

export function isMetricEditor(id) {
  return Boolean(METRIC_EDITORS[id])
}
