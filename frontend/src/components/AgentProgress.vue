<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { formatElapsed, progressRows, progressStepLabel, progressSummary, stepElapsedMs } from '../features/assistant/progress'
import UiIcon from './UiIcon.vue'

const props = defineProps({
  steps: { type: Array, default: () => [] },
  status: { type: String, default: 'streaming' },
})

const active = computed(() => props.status === 'pending' || props.status === 'streaming')
const summary = computed(() => progressSummary(props.status, props.steps))
const rows = computed(() => progressRows(props.steps, props.status))
const clock = ref(Date.now())
let timer
watch(active, (value) => {
  clearInterval(timer)
  clock.value = Date.now()
  if (value) timer = setInterval(() => { clock.value = Date.now() }, 1000)
}, { immediate: true })
onBeforeUnmount(() => clearInterval(timer))
const stateLabels = { running: '进行中', completed: '已完成', failed: '未完成', waiting: '待确认', skipped: '已跳过' }
const requestLabel = computed(() => active.value ? '进行中' : props.status === 'confirming' ? '待确认' : props.status === 'completed' ? '已完成' : props.status === 'stopped' ? '已停止' : '未完成')
const finishedCount = computed(() => rows.value.filter((step) => step.status === 'completed').length)
const slow = computed(() => active.value && rows.value.some((step) => step.status === 'running' && stepElapsedMs(step, clock.value) >= 20000))
const totalElapsed = computed(() => {
  const timed = rows.value.filter((step) => Number.isFinite(step.receivedAt))
  if (!timed.length) return null
  const start = Math.min(...timed.map((step) => step.receivedAt))
  const finish = active.value ? clock.value : Math.max(...timed.map((step) => step.receivedAt + (step.elapsedMs || 0)))
  return formatElapsed(finish - start)
})
</script>

<template>
  <details class="agent-progress" :class="[`is-${status}`, { 'is-active': active }]" :open="active">
    <summary>
      <span class="agent-progress__signal" aria-hidden="true"><UiIcon name="loading" :size="20" /></span>
      <span class="agent-progress__summary">
        <strong role="status" aria-live="polite" aria-atomic="true">{{ summary }}</strong>
        <small>已完成 {{ finishedCount }} 项<span v-if="totalElapsed" aria-hidden="true"> · {{ totalElapsed }}</span></small>
      </span>
      <span class="agent-progress__state">{{ requestLabel }}</span>
    </summary>
    <ol class="agent-progress__steps" aria-label="助手处理步骤">
      <li
        v-for="step in rows"
        :key="step.id"
        :class="{
          'is-current': step.status === 'running',
          'is-done': step.status === 'completed',
          'is-failed': step.status === 'failed',
          'is-child': Boolean(step.parentId),
        }"
      >
        <span class="agent-progress__node" aria-hidden="true" />
        <span class="agent-progress__label">{{ progressStepLabel(step) }}</span>
        <span class="agent-progress__duration" aria-hidden="true">{{ formatElapsed(stepElapsedMs(step, clock)) }}</span>
        <span class="agent-progress__step-state">{{ stateLabels[step.status] }}</span>
      </li>
    </ol>
    <p v-if="slow" class="agent-progress__notice">当前步骤耗时较长，您可以继续等待，也可以停止生成。</p>
  </details>
</template>

<style scoped>
.agent-progress {
  width: min(650px, 100%);
  margin: 0 0 14px;
  border: 1px solid rgba(15, 143, 130, .18);
  border-radius: 16px;
  background: linear-gradient(135deg, rgba(246, 252, 251, .96), rgba(255, 255, 255, .94));
  box-shadow: 0 10px 30px rgba(23, 52, 59, .055);
  overflow: hidden;
}
.agent-progress summary {
  min-height: 64px;
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr) auto;
  align-items: center;
  gap: 11px;
  padding: 10px 14px;
  cursor: pointer;
  list-style: none;
}
.agent-progress summary::-webkit-details-marker { display: none; }
.agent-progress__signal {
  position: relative;
  width: 34px; height: 34px; display: grid; place-items: center;
  border-radius: 50%; background: var(--color-mint-100); color: var(--color-brand-700);
}
.agent-progress:not(.is-active) :deep(.logo-loader path) {
  animation: none;
  stroke-dashoffset: 0;
  opacity: 1;
}
.agent-progress__summary { min-width: 0; }
.agent-progress__summary strong, .agent-progress__summary small { display: block; }
.agent-progress__summary strong { color: var(--color-text); font-size: 14px; line-height: 1.4; }
.agent-progress__summary small { margin-top: 3px; color: var(--color-text-secondary); font-size: 12px; }
.agent-progress__state {
  padding: 4px 8px; border-radius: 999px; background: var(--color-mint-050);
  color: var(--color-brand-700); font-size: 11px; font-weight: 750; white-space: nowrap;
}
.agent-progress.is-error { border-color: rgba(194, 65, 54, .22); }
.agent-progress.is-error .agent-progress__signal { background: var(--color-danger-bg); color: var(--color-danger); }
.agent-progress.is-error .agent-progress__state { background: var(--color-danger-bg); color: var(--color-danger); }
.agent-progress__steps { display: grid; gap: 0; margin: 0; padding: 2px 16px 14px 31px; list-style: none; }
.agent-progress__steps li { position: relative; min-height: 32px; display: flex; align-items: center; padding-left: 24px; color: var(--color-text-secondary); font-size: 13px; }
.agent-progress__steps li:not(:last-child)::before { content: ''; position: absolute; left: 5px; top: 20px; bottom: -12px; width: 1px; background: var(--color-border-strong); }
.agent-progress__node { position: absolute; left: 0; width: 11px; height: 11px; border: 2px solid var(--color-border-strong); border-radius: 50%; background: #fff; }
.agent-progress__steps li.is-done .agent-progress__node { border-color: var(--color-brand-700); background: var(--color-brand-700); box-shadow: inset 0 0 0 2px #fff; }
.agent-progress__steps li.is-current { color: var(--color-text); font-weight: 700; }
.agent-progress__steps li.is-current .agent-progress__node { border-color: var(--color-brand-700); animation: agent-node 1.2s ease-in-out infinite; }
.agent-progress__label { flex: 1; min-width: 0; }
.agent-progress__duration { margin-left: 12px; font-size: 12px; font-variant-numeric: tabular-nums; white-space: nowrap; }
.agent-progress__step-state { width: 42px; margin-left: 10px; font-size: 11px; text-align: right; white-space: nowrap; }
.agent-progress__steps li { padding-right: 0; gap: 4px; }
.agent-progress__steps li.is-child { margin-left: 18px; }
.agent-progress__steps li.is-failed { color: var(--color-danger); }
.agent-progress__steps li.is-failed .agent-progress__node { border-color: var(--color-danger); }
.agent-progress__notice { margin: 0; padding: 11px 16px; border-top: 1px solid var(--color-border); color: var(--color-text-secondary); font-size: 12px; line-height: 1.6; }
@keyframes agent-node { 50% { box-shadow: 0 0 0 5px rgba(15, 143, 130, .12); } }
@media (max-width: 520px) {
  .agent-progress summary { grid-template-columns: 32px minmax(0, 1fr); }
  .agent-progress__state { grid-column: 2; justify-self: start; margin-top: -4px; }
}
@media (prefers-reduced-motion: reduce) {
  .agent-progress__steps li.is-current .agent-progress__node { animation: none; }
}
</style>
