<script setup>
import { useRoute } from 'vue-router'
import { MODE_AGENT, writeMode } from '../features/experience/mode'
import UiIcon from './UiIcon.vue'

const route = useRoute()
const tabs = [
  { to: '/home', icon: 'home', label: '首页' },
  { to: '/registration', icon: 'calendar', label: '挂号' },
  { to: '/department', icon: 'hospital', label: '科室' },
  { to: '/payment', icon: 'wallet', label: '缴费' },
  { to: '/user', icon: 'user', label: '我的' },
]
const active = (path) => route.path === path || route.path.startsWith(`${path}/`)
</script>

<template>
  <div class="mobile-tabbar">
    <RouterLink v-for="tab in tabs" :key="tab.to" :to="tab.to"
      class="mobile-tabbar__item" :class="{ 'mobile-tabbar__item--active': active(tab.to) }">
      <UiIcon :name="tab.icon" />
      <span>{{ tab.label }}</span>
    </RouterLink>
  </div>
  <RouterLink class="mobile-mode-switch" to="/assistant" @click="writeMode(MODE_AGENT)">AI 新版 →</RouterLink>
</template>
