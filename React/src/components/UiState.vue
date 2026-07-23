<script setup>
import UiIcon from './UiIcon.vue'

defineProps({
  loading: Boolean,
  error: { type: String, default: '' },
  empty: Boolean,
  emptyText: { type: String, default: '暂无数据' },
})
</script>

<template>
  <div v-if="loading" class="shared-loading">
    <div class="shared-loading__spinner" />
    <span class="shared-loading__text">加载中…</span>
  </div>
  <div v-else-if="error" class="card mb-md" style="color:var(--c-danger);text-align:center">{{ error }}</div>
  <div v-else-if="empty" class="shared-empty">
    <span class="shared-empty__icon"><UiIcon name="record" :size="48" /></span>
    <span class="shared-empty__text text-sub">{{ emptyText }}</span>
  </div>
  <slot v-else />
</template>
