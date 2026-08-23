<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import UiIcon from './UiIcon.vue'

const FOCUSABLE = 'button:not([disabled]), [href], input, select, textarea'
const router = useRouter()
const contextCollapsed = ref(false)
const historyOpen = ref(false)
const contextOpen = ref(false)
const historyPanel = ref(null)
const contextPanel = ref(null)
const drawerReturnFocus = ref(null)
let drawerPreviousOverflow = ''

const drawerQuery = window.matchMedia('(max-width: 1099px)')
const isDrawerLayout = ref(drawerQuery.matches)

function onDrawerQueryChange(event) {
  isDrawerLayout.value = event.matches
  if (!event.matches) closeDrawers(false)
}

function goHome() {
  router.push('/home')
}

const drawerType = computed(() => (historyOpen.value ? 'history' : contextOpen.value ? 'context' : null))

function drawerPanel(type = drawerType.value) {
  return type === 'history' ? historyPanel.value : contextPanel.value
}

function focusDrawer(type) {
  nextTick(() => {
    drawerPanel(type)?.querySelector(FOCUSABLE)?.focus()
  })
}

function lockBody() {
  if (historyOpen.value || contextOpen.value) return
  drawerReturnFocus.value = document.activeElement instanceof HTMLElement ? document.activeElement : null
  drawerPreviousOverflow = document.body.style.overflow
  document.body.style.overflow = 'hidden'
}

function unlockBody(restoreFocus) {
  document.body.style.overflow = drawerPreviousOverflow
  if (!restoreFocus) {
    drawerReturnFocus.value = null
    return
  }
  const target = drawerReturnFocus.value
  drawerReturnFocus.value = null
  nextTick(() => target?.isConnected && target.focus())
}

function openHistory() {
  if (!isDrawerLayout.value) return
  lockBody()
  historyOpen.value = true
  contextOpen.value = false
  focusDrawer('history')
}

function openContext() {
  if (!isDrawerLayout.value) return
  lockBody()
  contextOpen.value = true
  historyOpen.value = false
  focusDrawer('context')
}

function closeHistory(restoreFocus = true) {
  if (!historyOpen.value) return
  historyOpen.value = false
  if (!contextOpen.value) unlockBody(restoreFocus)
}

function closeContext(restoreFocus = true) {
  if (!contextOpen.value) return
  contextOpen.value = false
  if (!historyOpen.value) unlockBody(restoreFocus)
}

function closeDrawers(restoreFocus = true) {
  const open = historyOpen.value || contextOpen.value
  historyOpen.value = false
  contextOpen.value = false
  if (open) unlockBody(restoreFocus)
}

function onDrawerKeydown(event) {
  if (!isDrawerLayout.value || !drawerType.value) return
  if (event.key === 'Escape') {
    event.preventDefault()
    closeDrawers(true)
    return
  }
  if (event.key !== 'Tab') return
  const focusable = [...drawerPanel()?.querySelectorAll(FOCUSABLE) || []]
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

watch([drawerType, isDrawerLayout], ([type, drawer]) => {
  document.removeEventListener('keydown', onDrawerKeydown)
  if (type && drawer) document.addEventListener('keydown', onDrawerKeydown)
})

onMounted(() => {
  drawerQuery.addEventListener('change', onDrawerQueryChange)
})

onBeforeUnmount(() => {
  document.removeEventListener('keydown', onDrawerKeydown)
  drawerQuery.removeEventListener('change', onDrawerQueryChange)
  document.body.style.overflow = drawerPreviousOverflow
})

defineExpose({ openHistory, closeHistory, openContext, closeContext, closeDrawers })
</script>

<template>
  <div class="assistant-shell" :class="{ 'is-context-collapsed': contextCollapsed }">
    <header class="assistant-shell__header">
      <div class="assistant-shell__header-start">
        <button class="assistant-shell__back" type="button" @click="goHome">
          <UiIcon name="arrowLeft" :size="18" />返回
        </button>
        <button class="assistant-shell__brand" type="button" @click="goHome">
          <span class="assistant-shell__logo" aria-hidden="true"><UiIcon name="logo" :size="22" /></span>
          <span><strong>温润诊所</strong><small>患者服务</small></span>
        </button>
        <button
          class="assistant-shell__icon-btn assistant-shell__history-btn"
          type="button"
          aria-label="打开历史会话"
          :aria-expanded="historyOpen"
          @click="openHistory"
        >
          <UiIcon name="history" :size="18" />
        </button>
        <button
          class="assistant-shell__icon-btn assistant-shell__context-btn"
          type="button"
          aria-label="打开就诊资料"
          :aria-expanded="contextOpen"
          @click="openContext"
        >
          <UiIcon name="record" :size="18" />
        </button>
      </div>
      <p class="assistant-shell__title assistant-shell__title--desktop">温润健康助手</p>
      <p class="assistant-shell__title assistant-shell__title--compact">健康助手</p>
      <div class="assistant-shell__header-end">
        <button
          class="assistant-shell__collapse"
          type="button"
          :aria-expanded="!contextCollapsed"
          @click="contextCollapsed = !contextCollapsed"
        >
          <UiIcon name="panelRight" :size="18" />
          {{ contextCollapsed ? '展开就诊资料' : '收起就诊资料' }}
        </button>
        <button class="assistant-shell__return" type="button" @click="goHome">返回患者服务</button>
        <div class="assistant-shell__header-actions">
          <slot name="header-actions" />
        </div>
      </div>
    </header>

    <div class="assistant-shell__workspace">
      <div
        v-if="isDrawerLayout && drawerType"
        class="assistant-shell__backdrop"
        @mousedown="closeDrawers(true)"
      />
      <aside
        ref="historyPanel"
        class="assistant-shell__sidebar"
        :class="{ 'is-open': historyOpen }"
        :inert="isDrawerLayout && !historyOpen ? true : undefined"
        :role="isDrawerLayout && historyOpen ? 'dialog' : 'complementary'"
        :aria-modal="isDrawerLayout && historyOpen ? 'true' : undefined"
        aria-label="历史会话"
      >
        <div class="assistant-shell__panel-bar">
          <h2>历史会话</h2>
          <button class="assistant-shell__icon-btn" type="button" aria-label="关闭历史会话" @click="closeHistory(true)">×</button>
        </div>
        <div class="assistant-shell__panel-body">
          <slot name="sidebar" />
        </div>
      </aside>

      <section class="assistant-shell__chat">
        <div class="assistant-shell__chips">
          <slot name="chips" :open-context="openContext" />
        </div>
        <div class="assistant-shell__chat-body">
          <slot />
        </div>
      </section>

      <aside
        ref="contextPanel"
        class="assistant-shell__context"
        :class="{ 'is-open': contextOpen }"
        :inert="isDrawerLayout && !contextOpen ? true : undefined"
        :role="isDrawerLayout && contextOpen ? 'dialog' : 'complementary'"
        :aria-modal="isDrawerLayout && contextOpen ? 'true' : undefined"
        aria-label="就诊资料"
      >
        <div class="assistant-shell__panel-bar">
          <h2>就诊资料</h2>
          <button class="assistant-shell__icon-btn" type="button" aria-label="关闭就诊资料" @click="closeContext(true)">×</button>
        </div>
        <div class="assistant-shell__panel-body">
          <slot name="context" />
        </div>
      </aside>
    </div>
  </div>
</template>

<style scoped>
.assistant-shell {
  min-height: 100vh;
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--color-bg);
  overflow: hidden;
}
.assistant-shell__header {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
  align-items: center;
  gap: 8px;
  min-height: 64px;
  padding: 0 16px;
  border-bottom: 1px solid var(--color-border);
  background: var(--color-surface);
}
.assistant-shell__header-start,
.assistant-shell__header-end {
  display: flex;
  align-items: center;
  gap: 8px;
}
.assistant-shell__header-end {
  justify-content: flex-end;
}
.assistant-shell__brand,
.assistant-shell__back,
.assistant-shell__return,
.assistant-shell__collapse,
.assistant-shell__icon-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 44px;
  min-width: 44px;
  padding: 0 12px;
  border: 1px solid transparent;
  border-radius: 9px;
  background: transparent;
  color: var(--color-text);
  cursor: pointer;
  font: inherit;
}
.assistant-shell__brand {
  gap: 12px;
  padding-left: 4px;
  text-align: left;
}
.assistant-shell__brand strong,
.assistant-shell__brand small {
  display: block;
}
.assistant-shell__brand small {
  margin-top: 2px;
  color: var(--color-text-secondary);
  font-size: 12px;
}
.assistant-shell__logo {
  width: 40px;
  height: 40px;
  display: grid;
  place-items: center;
  border-radius: 8px;
  background: var(--color-brand-700);
  color: #fff;
}
.assistant-shell__back,
.assistant-shell__return,
.assistant-shell__collapse,
.assistant-shell__icon-btn {
  border-color: var(--color-border);
  background: var(--color-surface);
  color: var(--color-text-secondary);
}
.assistant-shell__back:hover,
.assistant-shell__return:hover,
.assistant-shell__collapse:hover,
.assistant-shell__icon-btn:hover,
.assistant-shell__brand:hover {
  border-color: var(--color-brand-600);
  color: var(--color-brand-700);
}
.assistant-shell__title {
  margin: 0;
  color: var(--color-text);
  font-size: 16px;
  font-weight: 700;
  text-align: center;
}
.assistant-shell__title--compact,
.assistant-shell__back,
.assistant-shell__history-btn,
.assistant-shell__context-btn,
.assistant-shell__header-actions {
  display: none;
}
.assistant-shell__header-actions :deep(.btn) {
  min-height: 44px;
}
.assistant-shell__workspace {
  position: relative;
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: 240px minmax(0, 1fr) 260px;
}
.assistant-shell__sidebar,
.assistant-shell__context {
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: auto;
  background: var(--color-surface);
}
.assistant-shell__sidebar {
  background: var(--color-mint-100);
  color: var(--color-text);
  border-right: 1px solid var(--color-border);
}
.assistant-shell__context {
  border-left: 1px solid var(--color-border);
}
.assistant-shell__panel-bar {
  display: none;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 16px 16px 0;
}
.assistant-shell__panel-bar h2 {
  margin: 0;
  font-size: 18px;
}
.assistant-shell__panel-body {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  padding: 16px;
}
.assistant-shell__chat {
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.assistant-shell__chips {
  display: none;
  gap: 8px;
  padding: 10px 16px 0;
  overflow-x: auto;
}
.assistant-shell__chat-body {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.assistant-shell__backdrop {
  position: fixed;
  inset: 0;
  z-index: 30;
  background: rgba(18, 52, 45, 0.18);
}
@media (min-width: 1100px) {
  .assistant-shell.is-context-collapsed .assistant-shell__workspace {
    grid-template-columns: 240px minmax(0, 1fr);
  }
  .assistant-shell.is-context-collapsed .assistant-shell__context {
    display: none;
  }
}
@media (max-width: 1099px) {
  .assistant-shell__brand,
  .assistant-shell__return,
  .assistant-shell__collapse,
  .assistant-shell__title--desktop {
    display: none;
  }
  .assistant-shell__back,
  .assistant-shell__history-btn,
  .assistant-shell__context-btn {
    display: inline-flex;
  }
  .assistant-shell__title--compact {
    display: block;
  }
  .assistant-shell__header-actions {
    display: flex;
  }
  .assistant-shell__workspace {
    display: block;
  }
  .assistant-shell__chat {
    height: 100%;
  }
  .assistant-shell__panel-bar {
    display: flex;
  }
  .assistant-shell__sidebar,
  .assistant-shell__context {
    position: fixed;
    top: 0;
    bottom: 0;
    z-index: 40;
    width: min(360px, calc(100% - 24px));
    border: 0;
    box-shadow: 0 18px 42px rgba(18, 52, 45, 0.18);
    visibility: hidden;
    pointer-events: none;
    transition: transform var(--motion-med) var(--ease-enter), visibility 0s linear var(--motion-med);
  }
  .assistant-shell__sidebar {
    left: 0;
    transform: translateX(-100%);
  }
  .assistant-shell__context {
    right: 0;
    left: auto;
    transform: translateX(100%);
  }
  .assistant-shell__sidebar.is-open,
  .assistant-shell__context.is-open {
    visibility: visible;
    pointer-events: auto;
    transform: translateX(0);
    transition: transform var(--motion-med) var(--ease-enter);
  }
}
@media (max-width: 767px) {
  .assistant-shell__context-btn {
    display: none;
  }
  .assistant-shell__chips {
    display: flex;
  }
}
@media (prefers-reduced-motion: reduce) {
  .assistant-shell__sidebar,
  .assistant-shell__context {
    transition: none;
  }
}
</style>
