const MAX_PROGRESS_STEPS = 80
const STEP_STATES = new Set(['running', 'completed', 'failed', 'waiting', 'skipped'])

export function appendProgressStep(steps, text) {
  const current = Array.isArray(steps) ? steps.filter(Boolean) : []
  if (text && typeof text === 'object') {
    if (typeof text.id !== 'string' || typeof text.label !== 'string' || !STEP_STATES.has(text.status)) return current
    const index = current.findIndex((step) => typeof step === 'object' && step.id === text.id)
    const previous = index >= 0 ? current[index] : null
    const elapsedMs = Number.isFinite(text.elapsedMs) ? Math.max(0, text.elapsedMs) : 0
    const next = {
      id: text.id, label: text.label.trim(), status: text.status, parentId: text.parentId || null,
      elapsedMs, receivedAt: previous?.receivedAt ?? Date.now() - elapsedMs,
    }
    if (!next.label) return current
    if (index >= 0) return current.map((step, position) => position === index ? next : step)
    return [...current, next].slice(-MAX_PROGRESS_STEPS)
  }
  const next = String(text || '').trim()
  if (!next || current.at(-1) === next) return current
  return [...current, next].slice(-MAX_PROGRESS_STEPS)
}

export function completeProgressSteps(steps) {
  if (steps?.some((step) => typeof step === 'object')) {
    return appendProgressStep(steps.map((step) => {
      if (typeof step !== 'object' || step.status !== 'running') return step
      return { ...step, status: 'completed', elapsedMs: Math.max(0, Date.now() - step.receivedAt) }
    }), { id: 'answer', label: '回答已生成', status: 'completed', elapsedMs: 0 })
  }
  return appendProgressStep(steps, '回答已生成')
}

export function interruptProgressSteps(steps, status, now = Date.now()) {
  return (steps || []).map((step) => {
    if (typeof step !== 'object' || step.status !== 'running') return step
    return { ...step, status: status === 'confirming' ? 'waiting' : 'failed', elapsedMs: stepElapsedMs(step, now) }
  })
}

export function progressStepLabel(text) {
  return String((typeof text === 'object' ? text?.label : text) || '')
    .replace(/^正在/, '')
    .replace(/[.…]+$/, '')
    .trim()
}

export function progressSummary(status, steps) {
  const list = Array.isArray(steps) ? steps : []
  if (status === 'error') return '处理未完成'
  if (status === 'stopped') return '已停止生成'
  if (status === 'confirming') return '等待您的确认'
  if (status === 'completed') return list.some((step) => step?.status === 'failed') ? '回答已生成，部分查询未完成' : '已完成处理'
  const running = list.filter((step) => typeof step === 'object' && step.status === 'running')
  if (running.length) return `正在${progressStepLabel(running.at(-1))}…`
  return progressStepLabel(list.at(-1)) || '正在准备回答…'
}

export function progressRows(steps, status) {
  const active = status === 'pending' || status === 'streaming'
  return (steps || []).map((step, index) => {
    if (typeof step === 'string') return {
      id: `legacy-${index}`, label: progressStepLabel(step),
      status: index < steps.length - 1 || status === 'completed' ? 'completed' : active ? 'running' : status === 'confirming' ? 'waiting' : 'failed',
    }
    if (!active && step.status === 'running') return { ...step, status: status === 'confirming' ? 'waiting' : status === 'completed' ? 'completed' : 'failed' }
    return step
  })
}

export function stepElapsedMs(step, now = Date.now()) {
  if (step.status === 'running' && Number.isFinite(step.receivedAt)) return Math.max(0, now - step.receivedAt)
  return Math.max(0, step.elapsedMs || 0)
}

export function formatElapsed(ms) {
  const seconds = Math.max(0, Math.floor(ms / 1000))
  return seconds < 60 ? `${seconds} 秒` : `${Math.floor(seconds / 60)} 分 ${seconds % 60} 秒`
}
