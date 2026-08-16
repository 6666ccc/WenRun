<script setup>
import { useRouter, useRoute } from "vue-router";
import { useAuth } from "../stores";
import { useIsPc } from "../composables/useIsPc";
import { MODE_AGENT, writeMode } from "../features/experience/mode";
import MobileTabbar from "./MobileTabbar.vue";
import UiIcon from "./UiIcon.vue";

defineProps({ padded: { type: Boolean, default: true } });
const router = useRouter();
const route = useRoute();
const isPc = useIsPc();
const { user, logout } = useAuth();
const nav = [
  { to: "/home", icon: "home", label: "首页" },
  { to: "/registration", icon: "calendar", label: "预约挂号" },
  { to: "/department", icon: "hospital", label: "科室查询" },
  { to: "/payment", icon: "wallet", label: "门诊缴费" },
  { to: "/user", icon: "user", label: "个人中心" },
];
const active = (path) =>
  route.path === path || route.path.startsWith(`${path}/`);
async function signOut() {
  await logout();
  router.replace("/login");
}
function switchAgent() {
  writeMode(MODE_AGENT);
  router.push("/assistant");
}
</script>

<template>
  <div v-if="isPc" class="layout-pc">
    <div class="amber-line" />
    <aside class="layout-pc__sidebar glass-sidebar">
      <div class="vue-brand">
        <span class="vue-brand__logo"><UiIcon name="logo" :size="22" /></span>
        <div><strong>温润诊所</strong><small>WARM CLINIC</small></div>
      </div>
      <nav class="vue-nav">
        <RouterLink
          v-for="item in nav"
          :key="item.to"
          :to="item.to"
          class="pc-nav-link"
          :class="{ 'pc-nav-link--active': active(item.to) }"
        >
          <UiIcon :name="item.icon" />{{ item.label }}
        </RouterLink>
        <button
          class="pc-nav-link pc-nav-link--accent"
          :class="{ 'pc-nav-link--active': active('/assistant') }"
          @click="switchAgent"
        >
          <UiIcon name="ai" />AI 助手
        </button>
      </nav>
      <div class="vue-user">
        <div class="view-avatar-ring">
          <div class="view-avatar-ring__inner">
            {{ (user?.realName || user?.username || "?")[0] }}
          </div>
        </div>
        <strong>{{ user?.realName || user?.username || "患者" }}</strong>
        <button class="pc-nav-link" @click="signOut">
          <UiIcon name="logout" />退出登录
        </button>
      </div>
    </aside>
    <div class="layout-pc__main">
      <header class="vue-topbar">
        <span>温润诊所 · 患者自助服务</span>
        <button class="btn btn--outline btn--sm" @click="switchAgent">
          AI 新版
        </button>
      </header>
      <div class="layout-pc__content"><slot /></div>
      <footer class="vue-footer">
        温润诊所 Warm Clinic © 2026 · 本系统仅供演示
      </footer>
    </div>
  </div>
  <div v-else class="page">
    <slot />
    <MobileTabbar />
  </div>
</template>

<style>
.vue-brand {
  padding: 20px 24px;
  border-bottom: 1px solid var(--c-border-light);
  display: flex;
  align-items: center;
  gap: 12px;
}
.vue-brand__logo {
  width: 40px;
  height: 40px;
  border-radius: var(--radius);
  background: linear-gradient(135deg, #3d5a5c, #556f71);
  color: #fff;
  display: grid;
  place-items: center;
}
.vue-brand strong,
.vue-brand small {
  display: block;
}
.vue-brand strong {
  font-family: var(--font-serif);
  color: var(--c-brand);
}
.vue-brand small {
  font-size: 0.7rem;
  color: var(--c-muted);
}
.vue-nav {
  padding: 12px;
  flex: 1;
}
.vue-nav .pc-nav-link--accent {
  margin-top: 12px;
  width: 100%;
}
.vue-user {
  padding: 16px 24px;
  border-top: 1px solid var(--c-border-light);
}
.vue-user .view-avatar-ring {
  width: 40px;
  height: 40px;
  margin: 0 0 8px;
}
.vue-user .pc-nav-link {
  margin-top: 10px;
}
.vue-topbar {
  height: var(--header-h);
  border-bottom: 1px solid var(--c-border-light);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 28px;
  color: var(--c-sub);
  background: rgba(255, 253, 249, 0.7);
  backdrop-filter: blur(12px);
}
.vue-footer {
  border-top: 1px solid var(--c-border-light);
  padding: 12px 28px;
  font-size: 0.75rem;
  color: var(--c-muted);
}
</style>
