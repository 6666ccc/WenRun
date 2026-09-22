const MAX_PROGRESS_STEPS = 6

export function appendProgressStep(steps, text) {
  const current = Array.isArray(steps) ? steps.filter(Boolean) : []
  const next = String(text || '').trim()
  if (!next || current.at(-1) === next) return current
  return [...current, next].slice(-MAX_PROGRESS_STEPS)
}

export function completeProgressSteps(steps) {
  return appendProgressStep(steps, '回答已生成')
}

export function progressStepLabel(text) {
  return String(text || '')
    .replace(/^正在/, '')
    .replace(/[.…]+$/, '')
    .trim()
}

export function progressSummary(status, steps) {
  const list = Array.isArray(steps) ? steps : []
  if (status === 'error') return '处理未完成'
  if (status === 'stopped') return '已停止生成'
  if (status === 'confirming') return '等待您的确认'
  if (status === 'completed') return '已完成处理'
  return list.at(-1) || '正在准备回答…'
}
