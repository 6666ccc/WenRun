<script setup>
import { useRoute } from 'vue-router'
import UiIcon from './UiIcon.vue'

const route = useRoute()
const tabs = [
  { to: '/home', icon: 'home', label: '首页' },
  { to: '/registration', icon: 'calendar', label: '挂号' },
  { to: '/assistant', icon: 'ai', label: '助手' },
  { to: '/payment', icon: 'wallet', label: '缴费' },
  { to: '/user', icon: 'user', label: '我的' },
]
const active = (path) => route.path === path || route.path.startsWith(`${path}/`)
</script>

<template>
  <nav class="mobile-tabbar" aria-label="患者端主导航">
    <RouterLink v-for="tab in tabs" :key="tab.to" :to="tab.to"
      class="mobile-tabbar__item" :class="{ 'mobile-tabbar__item--active': active(tab.to) }" :aria-current="active(tab.to) ? 'page' : undefined">
      <UiIcon :name="tab.icon" :size="22" />
      <span>{{ tab.label }}</span>
    </RouterLink>
  </nav>
</template>
