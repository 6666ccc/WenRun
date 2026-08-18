<script setup>
import { computed } from 'vue'
import { interruptSummary } from '../features/assistant/interrupt.js'

const props = defineProps({
  interrupt: { type: Object, required: true },
  loading: Boolean,
})

const emit = defineEmits(['confirm', 'reject'])

const params = computed(() => props.interrupt?.params || {})
const slot = computed(() => params.value.slot || params.value)
const rows = computed(() => [
  { label: '患者', value: params.value.patientName || params.value.patientId },
  { label: '科室', value: slot.value.deptName },
  { label: '医生', value: slot.value.staffName },
  { label: '日期', value: slot.value.workDate },
  { label: '时段', value: slot.value.timePeriod },
  { label: '费用', value: slot.value.registerFee == null || slot.value.registerFee === '' ? '' : `¥${slot.value.registerFee}` },
].filter((row) => row.value != null && row.value !== ''))
</script>

<template>
  <section class="assistant-interrupt" role="dialog" aria-label="确认挂号">
    <small>请确认这次挂号</small>
    <h3>{{ interruptSummary(interrupt) }}</h3>
    <dl v-if="rows.length">
      <div v-for="row in rows" :key="row.label">
        <dt>{{ row.label }}</dt>
        <dd>{{ row.value }}</dd>
      </div>
    </dl>
    <div class="assistant-interrupt__actions">
      <button type="button" :disabled="loading" @click="emit('reject')">返回修改</button>
      <button type="button" class="is-primary" :disabled="loading" @click="emit('confirm')">
        {{ loading ? '正在提交…' : '确认挂号' }}
      </button>
    </div>
  </section>
</template>
