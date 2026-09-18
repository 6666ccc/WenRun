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
  { to: '/assistant', icon: 'ai', label: 'AI 健康助手' },
  { to: '/registration', icon: 'calendar', label: '预约挂号' },
  { to: '/user', icon: 'user', label: '个人中心' },
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
    <a class="skip-link" href="#main-content">跳到主要内容</a>
    <aside class="app-shell__sidebar" aria-label="患者服务导航">
      <RouterLink class="app-shell__brand" to="/home" aria-label="温润医院患者服务首页">
        <span class="app-shell__logo" aria-hidden="true"><UiIcon name="logo" :size="22" /></span>
        <div class="app-shell__brand-text"><small>WENRUN CARE</small><strong>温润医院</strong><span>患者服务</span></div>
      </RouterLink>

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
          <span><strong>{{ user?.realName || user?.username || '患者' }}</strong><small>查看个人中心</small></span>
        </RouterLink>
        <button class="app-shell__logout" type="button" @click="signOut"><UiIcon name="logout" :size="18" />退出登录</button>
      </div>
    </aside>

    <div class="app-shell__main">
      <header class="app-shell__topbar">
        <div class="app-shell__topbar-inner">
          <nav aria-label="面包屑"><span class="app-shell__breadcrumb">患者服务</span><span class="app-shell__separator">/</span><strong>{{ pageLabel }}</strong></nav>
          <span class="app-shell__emergency"><UiIcon name="alert" :size="16" />急症请拨打 120</span>
        </div>
      </header>
      <main id="main-content" class="app-shell__content" :class="{ 'app-shell__content--flush': !padded }" tabindex="-1">
        <Transition name="clinic-page" mode="out-in">
          <div :key="route.fullPath" class="app-shell__page"><slot /></div>
        </Transition>
      </main>
      <footer class="app-shell__footer"><div class="app-shell__footer-inner"><span>温润医院 · 患者端服务</span><span>本系统仅供演示 · 紧急情况请及时就医</span></div></footer>
    </div>
  </div>

  <div v-else class="mobile-shell">
    <a class="skip-link" href="#main-content">跳到主要内容</a>
    <main id="main-content" class="mobile-shell__content" :class="{ 'mobile-shell__content--flush': !padded }" tabindex="-1">
      <Transition name="clinic-page" mode="out-in">
        <div :key="route.fullPath" class="mobile-shell__page"><slot /></div>
      </Transition>
    </main>
    <MobileTabbar />
  </div>
</template>

<style>
.skip-link { position: fixed; top: 10px; left: 12px; z-index: 10000; padding: 10px 14px; border-radius: 8px; background: #fff; color: var(--color-brand-900); font-weight: 700; box-shadow: var(--shadow-lg); transform: translateY(-160%); transition: transform var(--motion-fast) var(--ease-enter); }
.skip-link:focus { transform: translateY(0); }
.app-shell { min-height: 100vh; display: flex; background: var(--color-bg); }
.app-shell__sidebar {
  position: sticky;
  top: 0;
  width: 232px;
  height: 100vh;
  min-height: 100vh;
  max-height: 100vh;
  flex: 0 0 232px;
  align-self: flex-start;
  display: flex;
  flex-direction: column;
  overflow-x: hidden;
  overflow-y: auto;
  background: var(--color-sidebar);
  color: var(--color-sidebar-text);
}
.app-shell__sidebar::after { content: ''; position: absolute; top: 104px; bottom: 126px; left: 29px; width: 1px; background: linear-gradient(transparent, rgba(157,226,214,.36) 12%, rgba(157,226,214,.36) 88%, transparent); pointer-events: none; }
.app-shell__brand { position: relative; z-index: 1; display: flex; align-items: center; gap: 12px; min-height: 84px; padding: 17px 18px; border-bottom: 1px solid rgba(255,255,255,.13); color: #fff; text-decoration: none; }
.app-shell__logo { width: 42px; height: 42px; display: grid; place-items: center; flex: 0 0 42px; border: 1px solid rgba(255,255,255,.22); border-radius: 12px; background: rgba(255,255,255,.11); color: #fff; }
.app-shell__brand-text strong, .app-shell__brand-text small, .app-shell__brand-text span, .app-shell__account-link strong, .app-shell__account-link small { display: block; }
.app-shell__brand-text small { margin-bottom: 3px; color: #9de2d6; font-family: var(--font-utility); font-size: 10px; font-weight: 700; letter-spacing: .14em; }
.app-shell__brand-text strong { color: #fff; font-size: 18px; line-height: 1.2; letter-spacing: .02em; }
.app-shell__brand-text span { margin-top: 3px; color: var(--color-sidebar-muted); font-size: 12px; }
.app-shell__nav { position: relative; z-index: 1; display: grid; gap: 7px; padding: 22px 11px; }
.app-shell__nav-link { position: relative; display: flex; align-items: center; gap: 13px; min-height: 50px; padding: 0 15px; border: 1px solid transparent; border-radius: 10px; color: rgba(255,255,255,.8); font-size: 15px; text-decoration: none; transition: background-color 180ms var(--ease-standard), border-color 180ms var(--ease-standard), color 180ms var(--ease-standard), transform 180ms var(--ease-standard); }
.app-shell__nav-link::before { content: ''; position: absolute; left: -13px; width: 4px; height: 18px; opacity: 0; border-radius: 0 4px 4px 0; background: #9de2d6; transition: height var(--motion-fast) var(--ease-standard), opacity var(--motion-fast) var(--ease-standard); }
.app-shell__nav-link:hover, .app-shell__nav-link:focus-visible { border-color: rgba(255,255,255,.12); background: rgba(255,255,255,.09); color: #fff; }
.app-shell__nav-link.is-active { border-color: rgba(255,255,255,.18); background: rgba(255,255,255,.15); color: #fff; font-weight: 700; }
.app-shell__nav-link.is-active::before { height: 28px; opacity: 1; }
.app-shell__nav-link svg { transition: transform 180ms var(--ease-standard); }
.app-shell__nav-link:hover svg, .app-shell__nav-link:focus-visible svg { transform: translateX(2px); }
.app-shell__account { position: relative; z-index: 1; margin-top: auto; padding: 18px 16px 22px; border-top: 1px solid rgba(255,255,255,.13); background: rgba(0,0,0,.08); }
.app-shell__account-link { display: flex; align-items: center; gap: 10px; color: #fff; text-decoration: none; }
.app-shell__avatar { width: 40px; height: 40px; display: grid; place-items: center; flex: 0 0 40px; border: 1px solid rgba(255,255,255,.2); border-radius: 12px; background: rgba(255,255,255,.14); color: #fff; font-weight: 700; }
.app-shell__account-link strong { font-size: 14px; }
.app-shell__account-link small { margin-top: 2px; color: var(--color-sidebar-muted); font-size: 12px; }
.app-shell__logout { display: flex; align-items: center; gap: 8px; width: 100%; min-height: 44px; margin-top: 12px; padding: 0 10px; border: 0; border-radius: 8px; background: transparent; color: var(--color-sidebar-muted); cursor: pointer; font: inherit; text-align: left; }
.app-shell__logout:hover, .app-shell__logout:focus-visible { background: rgba(255,255,255,.1); color: #fff; }
.app-shell__main { min-width: 0; min-height: 100vh; flex: 1; display: flex; flex-direction: column; }
.app-shell__topbar { position: sticky; top: 0; z-index: 20; min-height: 64px; border-bottom: 1px solid var(--color-border); background: rgba(255,255,255,.92); backdrop-filter: blur(14px); }
.app-shell__topbar-inner { width: min(1360px, 100%); min-height: 64px; display: flex; align-items: center; justify-content: space-between; gap: 24px; margin: 0 auto; padding: 0 40px; }
.app-shell__breadcrumb { color: var(--color-text-secondary); font-size: 14px; }
.app-shell__separator { margin: 0 10px; color: var(--color-border-strong); }
.app-shell__topbar strong { color: var(--color-text); font-size: 14px; font-weight: 700; }
.app-shell__emergency { display: inline-flex; align-items: center; gap: 7px; min-height: 36px; padding: 0 12px; border: 1px solid #efc9a1; border-radius: 999px; background: #fff8ef; color: #7c4a12; font-size: 13px; font-weight: 600; }
.app-shell__content { width: min(1360px, 100%); flex: 1; margin: 0 auto; padding: 34px 40px 42px; }
.app-shell__content--flush { width: 100%; max-width: none; padding: 0; }
.app-shell__page { min-height: 100%; }
.app-shell__footer { border-top: 1px solid var(--color-border); color: var(--color-text-muted); font-size: 12px; background: rgba(255,255,255,.76); }
.app-shell__footer-inner { width: min(1360px, 100%); min-height: 48px; display: flex; align-items: center; justify-content: space-between; gap: 20px; margin: 0 auto; padding: 10px 40px; }
.mobile-shell { min-height: 100%; background: var(--color-bg); }
.mobile-shell__content { min-height: 100vh; padding: 20px 16px calc(84px + env(safe-area-inset-bottom)); }
.mobile-shell__content--flush { padding: 0 0 calc(84px + env(safe-area-inset-bottom)); }
@media (min-width: 768px) and (max-width: 1199px) {
  .app-shell__sidebar { width: 80px; flex-basis: 80px; }
  .app-shell__brand { justify-content: center; padding: 18px 12px; }
  .app-shell__brand-text, .app-shell__nav-link span, .app-shell__account-link > span:last-child, .app-shell__logout, .app-shell__sidebar::after { display: none; }
  .app-shell__nav-link { justify-content: center; padding: 0; }
  .app-shell__nav-link::before { left: -13px; }
  .app-shell__account { padding: 16px 12px; }
  .app-shell__account-link { justify-content: center; }
  .app-shell__topbar-inner, .app-shell__footer-inner { padding-inline: 28px; }
  .app-shell__content { padding: 30px 28px 38px; }
}
@media (max-width: 767px) { .app-shell__footer { display: none; } }
@media (max-width: 520px) {
  .mobile-shell__content { padding-inline: 14px; }
  .mobile-shell__content--flush { padding-inline: 0; }
}
</style>
