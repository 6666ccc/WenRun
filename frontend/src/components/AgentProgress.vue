<script setup>
import { computed } from 'vue'
import { progressStepLabel, progressSummary } from '../features/assistant/progress'
import UiIcon from './UiIcon.vue'

const props = defineProps({
  steps: { type: Array, default: () => [] },
  status: { type: String, default: 'streaming' },
})

const active = computed(() => props.status === 'pending' || props.status === 'streaming')
const completed = computed(() => props.status === 'completed' || props.status === 'confirming')
const summary = computed(() => progressSummary(props.status, props.steps))
</script>

<template>
  <details class="agent-progress" :class="[`is-${status}`, { 'is-active': active }]" :open="active">
    <summary>
      <span class="agent-progress__signal" aria-hidden="true"><UiIcon name="activity" :size="16" /></span>
      <span class="agent-progress__summary">
        <strong>{{ summary }}</strong>
        <small>{{ active ? '处理进度会自动更新' : `处理过程 · ${steps.length} 步` }}</small>
      </span>
      <span class="agent-progress__state">{{ active ? '进行中' : completed ? '已完成' : status === 'error' ? '未完成' : '已停止' }}</span>
    </summary>
    <ol class="agent-progress__steps" aria-label="助手处理步骤">
      <li
        v-for="(step, index) in steps"
        :key="`${index}-${step}`"
        :class="{
          'is-current': active && index === steps.length - 1,
          'is-done': !active || index < steps.length - 1,
        }"
      >
        <span class="agent-progress__node" aria-hidden="true" />
        <span>{{ progressStepLabel(step) }}</span>
      </li>
    </ol>
  </details>
</template>

<style scoped>
.agent-progress {
  width: min(560px, 100%);
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
.agent-progress.is-active .agent-progress__signal::after {
  content: ''; position: absolute; inset: -4px; border: 1px solid rgba(15, 143, 130, .28); border-radius: inherit;
  animation: agent-signal 1.8s ease-out infinite;
}
.agent-progress__summary { min-width: 0; }
.agent-progress__summary strong, .agent-progress__summary small { display: block; }
.agent-progress__summary strong { color: var(--color-text); font-size: 14px; line-height: 1.4; }
.agent-progress__summary small { margin-top: 3px; color: var(--color-text-secondary); font-size: 11px; }
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
@keyframes agent-signal { from { opacity: .8; transform: scale(.86); } to { opacity: 0; transform: scale(1.35); } }
@keyframes agent-node { 50% { box-shadow: 0 0 0 5px rgba(15, 143, 130, .12); } }
@media (max-width: 520px) {
  .agent-progress summary { grid-template-columns: 32px minmax(0, 1fr); }
  .agent-progress__state { grid-column: 2; justify-self: start; margin-top: -4px; }
}
@media (prefers-reduced-motion: reduce) {
  .agent-progress.is-active .agent-progress__signal::after, .agent-progress__steps li.is-current .agent-progress__node { animation: none; }
}
</style>
