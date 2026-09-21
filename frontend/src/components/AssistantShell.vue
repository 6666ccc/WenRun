<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth } from '../stores'
import UiIcon from './UiIcon.vue'

const FOCUSABLE = 'button:not([disabled]), [href], input, select, textarea'
const router = useRouter()
const { user, logout } = useAuth()
const displayName = computed(() => user.value?.realName || user.value?.username || '患者')
const initial = computed(() => displayName.value[0])

async function signOut() {
  await logout()
  router.replace('/login')
}
const sidebarCollapsed = ref(false)
const historyOpen = ref(false)
const contextOpen = ref(false)
const historyPanel = ref(null)
const contextPanel = ref(null)
const drawerReturnFocus = ref(null)
let drawerPreviousOverflow = ''

const drawerQuery = window.matchMedia('(max-width: 959px)')
const isDrawerLayout = ref(drawerQuery.matches)

function onDrawerQueryChange(event) {
  isDrawerLayout.value = event.matches
  if (!event.matches) closeHistory(false)
}

const overlayOpen = computed(() => contextOpen.value || (isDrawerLayout.value && historyOpen.value))
const drawerType = computed(() => {
  if (contextOpen.value) return 'context'
  if (isDrawerLayout.value && historyOpen.value) return 'history'
  return null
})

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
  if (!isDrawerLayout.value) {
    sidebarCollapsed.value = false
    return
  }
  lockBody()
  historyOpen.value = true
  contextOpen.value = false
  focusDrawer('history')
}

function openContext() {
  if (contextOpen.value) return
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

function toggleSidebar() {
  if (isDrawerLayout.value) {
    if (historyOpen.value) closeHistory(true)
    else openHistory()
    return
  }
  sidebarCollapsed.value = !sidebarCollapsed.value
}

function onDrawerKeydown(event) {
  if (!drawerType.value) return
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

watch(drawerType, (type) => {
  document.removeEventListener('keydown', onDrawerKeydown)
  if (type) document.addEventListener('keydown', onDrawerKeydown)
})

onMounted(() => {
  drawerQuery.addEventListener('change', onDrawerQueryChange)
})

onBeforeUnmount(() => {
  document.removeEventListener('keydown', onDrawerKeydown)
  drawerQuery.removeEventListener('change', onDrawerQueryChange)
  document.body.style.overflow = drawerPreviousOverflow
})

defineExpose({ openHistory, closeHistory, openContext, closeContext, closeDrawers, toggleSidebar })
</script>

<template>
  <div class="assistant-shell" :class="{ 'is-sidebar-collapsed': sidebarCollapsed, 'is-drawer': isDrawerLayout }">
    <a class="assistant-shell__skip" href="#assistant-main">跳到对话</a>
    <div class="assistant-shell__workspace">
      <div
        v-if="overlayOpen"
        class="assistant-shell__backdrop"
        @mousedown="closeDrawers(true)"
      />

      <aside
        ref="historyPanel"
        class="assistant-shell__sidebar"
        :class="{ 'is-open': historyOpen }"
        :inert="isDrawerLayout && !historyOpen ? true : undefined"
        :role="isDrawerLayout && historyOpen ? 'dialog' : 'navigation'"
        :aria-modal="isDrawerLayout && historyOpen ? 'true' : undefined"
        aria-label="会话"
      >
        <div class="assistant-shell__sidebar-top">
          <button class="assistant-shell__icon" type="button" :aria-label="isDrawerLayout ? '关闭会话栏' : '收起会话栏'" @click="toggleSidebar">
            <UiIcon name="panelLeft" :size="18" />
          </button>
          <div class="assistant-shell__brand">
            <span class="assistant-shell__logo" aria-hidden="true"><UiIcon name="logo" :size="18" /></span>
            <span class="assistant-shell__brand-text">温润医院</span>
          </div>
        </div>
        <div class="assistant-shell__sidebar-body">
          <slot name="sidebar" />
        </div>
        <div class="assistant-shell__sidebar-foot">
          <nav class="assistant-shell__links" aria-label="患者服务">
            <RouterLink class="assistant-shell__link" to="/registration"><UiIcon name="calendar" :size="16" />预约挂号</RouterLink>
            <RouterLink class="assistant-shell__link" to="/archive"><UiIcon name="user" :size="16" />个人档案</RouterLink>
          </nav>
          <div class="assistant-shell__account">
            <span class="assistant-shell__avatar" aria-hidden="true">{{ initial }}</span>
            <strong>{{ displayName }}</strong>
            <button class="assistant-shell__logout" type="button" aria-label="退出登录" title="退出登录" @click="signOut">
              <UiIcon name="logout" :size="16" />
            </button>
          </div>
        </div>
      </aside>

      <section class="assistant-shell__chat">
        <header class="assistant-shell__chat-bar">
          <div class="assistant-shell__chat-start">
            <button
              v-if="isDrawerLayout || sidebarCollapsed"
              class="assistant-shell__icon"
              type="button"
              aria-label="打开会话栏"
              :aria-expanded="isDrawerLayout ? historyOpen : !sidebarCollapsed"
              @click="toggleSidebar"
            >
              <UiIcon name="panelLeft" :size="18" />
            </button>
            <div v-if="isDrawerLayout || sidebarCollapsed" class="assistant-shell__chat-new">
              <slot name="header-actions" />
            </div>
          </div>
          <p class="assistant-shell__title">温润健康助手</p>
          <button
            class="assistant-shell__icon assistant-shell__docs"
            type="button"
            aria-label="打开就诊资料"
            title="就诊资料"
            :aria-expanded="contextOpen"
            @click="openContext"
          >
            <UiIcon name="record" :size="18" />
            <span v-if="!isDrawerLayout" class="assistant-shell__docs-text">资料</span>
          </button>
        </header>
        <div id="assistant-main" class="assistant-shell__chat-body" tabindex="-1">
          <slot />
        </div>
      </section>

      <aside
        ref="contextPanel"
        class="assistant-shell__context"
        :class="{ 'is-open': contextOpen }"
        :inert="contextOpen ? undefined : true"
        :role="contextOpen ? 'dialog' : 'complementary'"
        :aria-modal="contextOpen ? 'true' : undefined"
        aria-label="就诊资料"
      >
        <div class="assistant-shell__panel-bar">
          <h2>就诊资料</h2>
          <button class="assistant-shell__icon" type="button" aria-label="关闭就诊资料" @click="closeContext(true)">
            <UiIcon name="arrowRight" :size="18" />
          </button>
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
  width: 100%;
  height: 100vh;
  min-height: 100vh;
  overflow: hidden;
  background: #fff;
  color: var(--color-text);
}

.assistant-shell__skip {
  position: fixed;
  top: 10px;
  left: 12px;
  z-index: 10000;
  padding: 10px 14px;
  border-radius: 8px;
  background: #fff;
  color: var(--color-brand-900);
  font-weight: 700;
  box-shadow: 0 10px 28px rgba(16, 42, 46, .14);
  transform: translateY(-160%);
}

.assistant-shell__skip:focus {
  transform: translateY(0);
}

.assistant-shell__workspace {
  position: relative;
  display: grid;
  grid-template-columns: 260px minmax(0, 1fr);
  width: 100%;
  height: 100%;
}

.assistant-shell.is-sidebar-collapsed .assistant-shell__workspace {
  grid-template-columns: minmax(0, 1fr);
}

.assistant-shell.is-sidebar-collapsed .assistant-shell__sidebar {
  display: none;
}

.assistant-shell__sidebar {
  display: flex;
  flex-direction: column;
  min-height: 0;
  background: #f7f8fa;
  color: var(--color-text);
  border-right: 1px solid #eef0f2;
}

.assistant-shell__sidebar-top {
  display: flex;
  align-items: center;
  gap: 2px;
  min-height: 52px;
  padding: 8px 10px 2px;
}

.assistant-shell__brand {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
  min-height: 40px;
  padding: 0 8px 0 4px;
  border-radius: 10px;
  color: var(--color-text);
  text-align: left;
}

.assistant-shell__logo {
  width: 28px;
  height: 28px;
  display: grid;
  place-items: center;
  flex: 0 0 28px;
  border-radius: 8px;
  background: var(--color-brand-800);
  color: #fff;
}

.assistant-shell__brand-text {
  overflow: hidden;
  color: var(--color-text);
  font-size: 15px;
  font-weight: 700;
  letter-spacing: .01em;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.assistant-shell__icon {
  display: grid;
  place-items: center;
  width: 40px;
  height: 40px;
  flex: 0 0 40px;
  border: 0;
  border-radius: 10px;
  background: transparent;
  color: var(--color-text-secondary);
  cursor: pointer;
}

.assistant-shell__icon:hover,
.assistant-shell__icon:focus-visible {
  background: rgba(16, 24, 32, .06);
  color: var(--color-text);
}

.assistant-shell__sidebar-body {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  padding: 4px 10px 12px;
  overflow: auto;
}

.assistant-shell__sidebar-foot {
  padding: 8px 10px 12px;
  border-top: 1px solid #eef0f2;
}

.assistant-shell__links {
  display: grid;
  gap: 2px;
}

.assistant-shell__link {
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 40px;
  padding: 0 10px;
  border-radius: 10px;
  color: var(--color-text);
  font-size: 14px;
  text-decoration: none;
}

.assistant-shell__link svg {
  color: var(--color-brand-700);
}

.assistant-shell__link:hover,
.assistant-shell__link:focus-visible {
  background: rgba(16, 24, 32, .06);
}

.assistant-shell__account {
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 44px;
  margin-top: 6px;
  padding: 0 4px 0 10px;
}

.assistant-shell__avatar {
  width: 30px;
  height: 30px;
  display: grid;
  place-items: center;
  flex: 0 0 30px;
  border-radius: 9px;
  background: var(--color-brand-800);
  color: #fff;
  font-size: 13px;
  font-weight: 700;
}

.assistant-shell__account strong {
  min-width: 0;
  flex: 1;
  overflow: hidden;
  font-size: 14px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.assistant-shell__logout {
  display: grid;
  place-items: center;
  width: 34px;
  height: 34px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: var(--color-text-secondary);
  cursor: pointer;
}

.assistant-shell__logout:hover,
.assistant-shell__logout:focus-visible {
  background: rgba(16, 24, 32, .06);
  color: var(--color-danger);
}

.assistant-shell__chat {
  min-width: 0;
  min-height: 0;
  width: 100%;
  display: flex;
  flex-direction: column;
  background: #fff;
}

.assistant-shell__chat-bar {
  display: grid;
  grid-template-columns: max-content minmax(0, 1fr) 40px;
  align-items: center;
  width: 100%;
  box-sizing: border-box;
  min-height: 52px;
  padding: 0 6px;
  background: #fff;
}

.assistant-shell__chat-start {
  display: flex;
  align-items: center;
  flex: 0 0 auto;
  gap: 2px;
}

.assistant-shell__chat-new {
  display: flex;
  align-items: center;
}

.assistant-shell__title {
  min-width: 0;
  margin: 0;
  overflow: hidden;
  color: var(--color-text);
  font-size: 15px;
  font-weight: 600;
  text-align: center;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.assistant-shell__docs {
  flex: 0 0 40px;
  flex-shrink: 0;
  justify-self: end;
}

.assistant-shell__docs-text {
  display: none;
}

@media (min-width: 960px) {
  .assistant-shell:not(.is-sidebar-collapsed) .assistant-shell__title {
    visibility: hidden;
  }

  .assistant-shell__docs {
    display: inline-flex;
    align-items: center;
    width: auto;
    min-width: 40px;
    flex-basis: auto;
    gap: 6px;
    padding: 0 10px;
    justify-self: end;
  }

  .assistant-shell__docs-text {
    display: inline;
    font-size: 13px;
  }

  .assistant-shell__chat-bar {
    grid-template-columns: max-content minmax(0, 1fr) max-content;
  }
}

.assistant-shell__chat-body {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.assistant-shell__context {
  position: fixed;
  top: 0;
  right: 0;
  bottom: 0;
  z-index: 40;
  display: flex;
  flex-direction: column;
  width: min(340px, calc(100% - 20px));
  background: #fff;
  box-shadow: -18px 0 40px rgba(16, 42, 46, .08);
  visibility: hidden;
  pointer-events: none;
  transform: translateX(100%);
  transition: transform var(--motion-med) var(--ease-enter), visibility 0s linear var(--motion-med);
}

.assistant-shell__context.is-open {
  visibility: visible;
  pointer-events: auto;
  transform: translateX(0);
  transition: transform var(--motion-med) var(--ease-enter);
}

.assistant-shell__panel-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-height: 56px;
  padding: 8px 12px 0 18px;
}

.assistant-shell__panel-bar h2 {
  margin: 0;
  font-size: 16px;
}

.assistant-shell__panel-body {
  flex: 1;
  min-height: 0;
  padding: 8px 18px 20px;
  overflow: auto;
}

.assistant-shell__backdrop {
  position: fixed;
  inset: 0;
  z-index: 30;
  background: rgba(16, 42, 46, .28);
}

@media (max-width: 959px) {
  .assistant-shell__workspace {
    display: block;
    width: 100%;
  }

  .assistant-shell__chat {
    width: 100%;
    height: 100%;
  }

.assistant-shell.is-drawer .assistant-shell__docs {
  position: fixed;
  top: 6px;
  right: 6px;
  z-index: 20;
  background: #fff;
  color: var(--color-text-secondary);
}

  .assistant-shell__sidebar {
    position: fixed;
    top: 0;
    bottom: 0;
    left: 0;
    z-index: 40;
    width: min(360px, 100%);
    border-right: 0;
    box-shadow: 18px 0 40px rgba(16, 42, 46, .1);
    visibility: hidden;
    pointer-events: none;
    transform: translateX(-100%);
    transition: transform var(--motion-med) var(--ease-enter), visibility 0s linear var(--motion-med);
  }

  .assistant-shell__sidebar.is-open {
    visibility: visible;
    pointer-events: auto;
    transform: translateX(0);
    transition: transform var(--motion-med) var(--ease-enter);
  }
}

@media (max-width: 767px) {
  .assistant-shell {
    --tabbar-height: calc(68px + env(safe-area-inset-bottom));
    height: calc(100dvh - var(--tabbar-height));
    min-height: calc(100dvh - var(--tabbar-height));
  }

  .assistant-shell__sidebar,
  .assistant-shell__context,
  .assistant-shell__backdrop {
    bottom: var(--tabbar-height);
  }
}

@media (prefers-reduced-motion: reduce) {
  .assistant-shell__sidebar,
  .assistant-shell__context {
    transition: none;
  }
}
</style>
