<script setup>
import { computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuth } from '../stores'
import { useIsPc } from '../composables/useIsPc'
import MobileTabbar from './MobileTabbar.vue'
import UiIcon from './UiIcon.vue'

defineProps({ padded: { type: Boolean, default: true } })

const router = useRouter()
const route = useRoute()
const isPc = useIsPc()
const { user, logout } = useAuth()

const nav = [
  { to: '/home', icon: 'home', label: '首页' },
  { to: '/assistant', icon: 'ai', label: '健康助手' },
  { to: '/registration', icon: 'calendar', label: '预约挂号' },
  { to: '/payment', icon: 'wallet', label: '门诊缴费' },
  { to: '/department', icon: 'hospital', label: '科室医生' },
  { to: '/user', icon: 'user', label: '我的档案' },
]
const pageLabel = computed(() => nav.find((item) => route.path === item.to || route.path.startsWith(`${item.to}/`))?.label || '患者服务')
const active = (path) => route.path === path || route.path.startsWith(`${path}/`)

async function signOut() {
  await logout()
  router.replace('/login')
}
</script>

<template>
  <div v-if="isPc" class="app-shell">
    <aside class="app-shell__sidebar">
      <div class="app-shell__brand">
        <span class="app-shell__logo" aria-hidden="true"><UiIcon name="logo" :size="22" /></span>
        <div><strong>温润诊所</strong><small>患者服务</small></div>
      </div>

      <nav class="app-shell__nav" aria-label="患者端主导航">
        <RouterLink
          v-for="item in nav"
          :key="item.to"
          :to="item.to"
          class="app-shell__nav-link"
          :class="{ 'is-active': active(item.to) }"
          :aria-current="active(item.to) ? 'page' : undefined"
        >
          <UiIcon :name="item.icon" :size="20" /><span>{{ item.label }}</span>
        </RouterLink>
      </nav>

      <div class="app-shell__account">
        <RouterLink to="/user" class="app-shell__account-link">
          <span class="app-shell__avatar" aria-hidden="true">{{ (user?.realName || user?.username || '患')[0] }}</span>
          <span><strong>{{ user?.realName || user?.username || '患者' }}</strong><small>查看我的档案</small></span>
        </RouterLink>
        <button class="app-shell__logout" type="button" @click="signOut"><UiIcon name="logout" :size="18" />退出登录</button>
      </div>
    </aside>

    <div class="app-shell__main">
      <header class="app-shell__topbar">
        <div><span class="app-shell__breadcrumb">温润诊所</span><span class="app-shell__separator">/</span><strong>{{ pageLabel }}</strong></div>
        <a class="app-shell__help" href="#main-content">需要帮助？</a>
      </header>
      <main id="main-content" class="app-shell__content"><slot /></main>
      <footer class="app-shell__footer">温润诊所 · 患者端服务 · 本系统仅供演示</footer>
    </div>
  </div>

  <div v-else class="mobile-shell">
    <main id="main-content" class="mobile-shell__content"><slot /></main>
    <MobileTabbar />
  </div>
</template>

<style>
.app-shell { min-height: 100vh; display: flex; background: var(--color-bg); }
.app-shell__sidebar { width: 248px; flex: 0 0 248px; min-height: 100vh; display: flex; flex-direction: column; background: var(--color-mint-100); color: var(--color-brand-900); border-right: 1px solid var(--color-border); }
.app-shell__brand { display: flex; align-items: center; gap: 12px; min-height: 88px; padding: 20px 24px; border-bottom: 1px solid var(--color-border); }
.app-shell__logo { width: 40px; height: 40px; display: grid; place-items: center; border-radius: 12px; background: var(--color-mint-500); color: var(--color-brand-900); }
.app-shell__brand strong, .app-shell__brand small, .app-shell__account-link strong, .app-shell__account-link small { display: block; }
.app-shell__brand strong { font-size: 17px; line-height: 1.4; color: var(--color-brand-900); }
.app-shell__brand small { margin-top: 2px; color: var(--color-text-secondary); font-size: 12px; }
.app-shell__nav { display: grid; gap: 4px; padding: 24px 12px; }
.app-shell__nav-link { position: relative; display: flex; align-items: center; gap: 12px; min-height: 48px; padding: 0 14px; border-radius: 10px; color: var(--color-text-secondary); font-size: 15px; text-decoration: none; transition: background-color var(--motion-fast) var(--ease-standard), color var(--motion-fast) var(--ease-standard); }
.app-shell__nav-link::before { content: ''; position: absolute; left: -12px; width: 3px; height: 0; opacity: 0; border-radius: 0 3px 3px 0; background: var(--color-brand-700); transition: height var(--motion-fast) var(--ease-standard), opacity var(--motion-fast) var(--ease-standard); }
.app-shell__nav-link:hover, .app-shell__nav-link:focus-visible { background: var(--color-mint-200); color: var(--color-brand-900); }
.app-shell__nav-link.is-active { background: var(--color-mint-300); color: var(--color-brand-900); font-weight: 700; }
.app-shell__nav-link.is-active::before { height: 28px; opacity: 1; }
.app-shell__account { margin-top: auto; padding: 18px 20px 22px; border-top: 1px solid var(--color-border); }
.app-shell__account-link { display: flex; align-items: center; gap: 10px; color: var(--color-brand-900); text-decoration: none; }
.app-shell__avatar { width: 38px; height: 38px; display: grid; place-items: center; flex: 0 0 38px; border-radius: 50%; background: var(--color-mint-500); color: var(--color-brand-900); font-weight: 700; }
.app-shell__account-link strong { font-size: 14px; }
.app-shell__account-link small { margin-top: 2px; color: var(--color-text-secondary); font-size: 12px; }
.app-shell__logout { display: flex; align-items: center; gap: 8px; width: 100%; min-height: 44px; margin-top: 12px; padding: 0 10px; border: 0; border-radius: 8px; background: transparent; color: var(--color-text-secondary); cursor: pointer; font: inherit; text-align: left; }
.app-shell__logout:hover, .app-shell__logout:focus-visible { background: var(--color-mint-200); color: var(--color-brand-900); }
.app-shell__main { min-width: 0; min-height: 100vh; flex: 1; display: flex; flex-direction: column; }
.app-shell__topbar { display: flex; align-items: center; justify-content: space-between; min-height: 64px; padding: 0 32px; border-bottom: 1px solid var(--color-border); background: var(--color-surface); }
.app-shell__breadcrumb { color: var(--color-text-secondary); }
.app-shell__separator { margin: 0 10px; color: var(--color-border-strong); }
.app-shell__topbar strong { color: var(--color-text); font-weight: 600; }
.app-shell__help { color: var(--color-brand-700); font-size: 14px; text-decoration: none; }
.app-shell__content { width: min(1180px, 100%); flex: 1; margin: 0 auto; padding: 32px; }
.app-shell__footer { padding: 14px 32px; border-top: 1px solid var(--color-border); color: var(--color-text-secondary); font-size: 12px; background: var(--color-surface); }
.mobile-shell { min-height: 100%; background: var(--color-bg); }
.mobile-shell__content { min-height: 100vh; padding: 16px 16px calc(80px + env(safe-area-inset-bottom)); }
@media (min-width: 768px) and (max-width: 1023px) {
  .app-shell__sidebar { width: 80px; flex-basis: 80px; }
  .app-shell__brand { justify-content: center; padding: 18px 12px; }
  .app-shell__brand > div, .app-shell__nav-link span, .app-shell__account-link > span:last-child, .app-shell__logout { display: none; }
  .app-shell__nav-link { justify-content: center; padding: 0; }
  .app-shell__nav-link.is-active::before { left: 0; }
  .app-shell__account { padding: 16px 12px; }
  .app-shell__account-link { justify-content: center; }
  .app-shell__content { padding: 24px; }
}
@media (max-width: 767px) { .app-shell__footer { display: none; } }
</style>
