<script setup>
import { nextTick, onBeforeUnmount, ref, useId, watch } from 'vue'

const props = defineProps({ show: Boolean, title: String, message: String, loading: Boolean })
const emit = defineEmits(['confirm', 'cancel'])
const dialog = ref(null)
const titleId = useId()
const descriptionId = useId()
let returnFocus = null
let previousOverflow = ''

function onKeydown(event) {
  if (!props.show) return
  if (event.key === 'Escape' && !props.loading) return emit('cancel')
  if (event.key !== 'Tab') return
  const focusable = [...dialog.value?.querySelectorAll('button:not([disabled]), [href], input, select, textarea') || []]
  if (!focusable.length) return
  const first = focusable[0]
  const last = focusable[focusable.length - 1]
  if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus() }
  else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus() }
}

watch(() => props.show, async (show) => {
  if (show) {
    returnFocus = document.activeElement
    previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    document.addEventListener('keydown', onKeydown)
    await nextTick()
    dialog.value?.querySelector('button:not([disabled])')?.focus()
  } else {
    document.removeEventListener('keydown', onKeydown)
    document.body.style.overflow = previousOverflow
    returnFocus?.focus?.()
  }
})
onBeforeUnmount(() => {
  document.removeEventListener('keydown', onKeydown)
  document.body.style.overflow = previousOverflow
})
</script>

<template>
  <Transition name="fade">
    <div v-if="show" class="shared-dialog-overlay" role="presentation" @click.self="!loading && emit('cancel')">
      <div ref="dialog" class="shared-dialog" role="dialog" aria-modal="true" :aria-labelledby="titleId" :aria-describedby="descriptionId" :aria-busy="loading">
        <h3 :id="titleId">{{ title || '确认操作' }}</h3>
        <p :id="descriptionId">{{ message }}</p>
        <div class="shared-dialog__actions">
          <button class="btn btn--ghost" type="button" :disabled="loading" @click="emit('cancel')">取消</button>
          <button class="btn btn--primary" type="button" :disabled="loading" @click="emit('confirm')">
            {{ loading ? '处理中…' : '确认' }}
          </button>
        </div>
      </div>
    </div>
  </Transition>
</template>
