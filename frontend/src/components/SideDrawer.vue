<script setup>
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'
import UiIcon from './UiIcon.vue'

const props = defineProps({
  open: { type: Boolean, default: false },
  title: { type: String, default: '' },
  backLabel: { type: String, default: '' },
})
const emit = defineEmits(['close', 'back'])

const FOCUSABLE = 'button:not([disabled]), [href], input, select, textarea'
const panel = ref(null)
let returnFocus = null
let previousOverflow = ''

function onKeydown(event) {
  if (!props.open) return
  if (event.key === 'Escape') {
    event.preventDefault()
    emit('close')
    return
  }
  if (event.key !== 'Tab') return
  const focusable = [...panel.value?.querySelectorAll(FOCUSABLE) || []]
  if (!focusable.length) return
  const first = focusable[0]
  const last = focusable[focusable.length - 1]
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault()
    last.focus()
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault()
    first.focus()
  }
}

watch(() => props.open, async (open) => {
  if (open) {
    returnFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null
    previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    document.addEventListener('keydown', onKeydown)
    await nextTick()
    panel.value?.querySelector(FOCUSABLE)?.focus()
  } else {
    document.removeEventListener('keydown', onKeydown)
    document.body.style.overflow = previousOverflow
    const target = returnFocus
    returnFocus = null
    nextTick(() => target?.isConnected && target.focus())
  }
}, { immediate: true })

onBeforeUnmount(() => {
  document.removeEventListener('keydown', onKeydown)
  if (props.open) document.body.style.overflow = previousOverflow
})
</script>

<template>
  <Teleport to="body">
    <Transition name="side-drawer">
      <div v-if="open" class="side-drawer" role="presentation">
        <div class="side-drawer__backdrop" @mousedown="emit('close')" />
        <section ref="panel" class="side-drawer__panel" role="dialog" aria-modal="true" :aria-label="title">
          <header class="side-drawer__bar">
            <button v-if="backLabel" class="side-drawer__back" type="button" @click="emit('back')">
              <UiIcon name="arrowLeft" :size="16" />{{ backLabel }}
            </button>
            <h2 class="side-drawer__title">{{ title }}</h2>
            <button class="side-drawer__close" type="button" aria-label="关闭" title="关闭" @click="emit('close')">
              <UiIcon name="arrowRight" :size="18" />
            </button>
          </header>
          <div class="side-drawer__body">
            <slot />
          </div>
        </section>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.side-drawer {
  position: fixed;
  inset: 0;
  z-index: 60;
}

.side-drawer__backdrop {
  position: absolute;
  inset: 0;
  background: rgba(16, 42, 46, .28);
}

.side-drawer__panel {
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  display: flex;
  flex-direction: column;
  width: min(720px, calc(100% - 40px));
  background: var(--color-bg);
  box-shadow: -18px 0 40px rgba(16, 42, 46, .12);
}

.side-drawer__bar {
  display: flex;
  align-items: center;
  gap: 12px;
  min-height: 60px;
  padding: 10px 14px 10px 24px;
  border-bottom: 1px solid var(--color-border);
  background: #fff;
}

.side-drawer__title {
  flex: 1;
  min-width: 0;
  margin: 0;
  overflow: hidden;
  font-size: 17px;
  font-weight: 700;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.side-drawer__back {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 36px;
  padding: 0 12px 0 8px;
  border: 1px solid var(--color-border);
  border-radius: 10px;
  background: #fff;
  color: var(--color-text-secondary);
  cursor: pointer;
  font: inherit;
  font-size: 13px;
}

.side-drawer__back:hover,
.side-drawer__back:focus-visible {
  border-color: var(--color-brand-600);
  color: var(--color-text);
}

.side-drawer__close {
  display: grid;
  place-items: center;
  width: 40px;
  height: 40px;
  border: 0;
  border-radius: 10px;
  background: transparent;
  color: var(--color-text-secondary);
  cursor: pointer;
}

.side-drawer__close:hover,
.side-drawer__close:focus-visible {
  background: rgba(16, 24, 32, .06);
  color: var(--color-text);
}

.side-drawer__body {
  flex: 1;
  min-height: 0;
  padding: 24px;
  overflow: auto;
}

.side-drawer-enter-active,
.side-drawer-leave-active { transition: opacity var(--motion-med) var(--ease-enter); }
.side-drawer-enter-active .side-drawer__panel,
.side-drawer-leave-active .side-drawer__panel { transition: transform var(--motion-med) var(--ease-enter); }
.side-drawer-enter-from,
.side-drawer-leave-to { opacity: 0; }
.side-drawer-enter-from .side-drawer__panel,
.side-drawer-leave-to .side-drawer__panel { transform: translateX(40px); }

@media (prefers-reduced-motion: reduce) {
  .side-drawer-enter-active,
  .side-drawer-leave-active,
  .side-drawer-enter-active .side-drawer__panel,
  .side-drawer-leave-active .side-drawer__panel { transition: none; }
}
</style>
