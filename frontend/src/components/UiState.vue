<script setup>
import { onBeforeUnmount, ref, watch } from 'vue'
import UiIcon from './UiIcon.vue'

const props = defineProps({
  loading: Boolean,
  error: { type: String, default: '' },
  empty: Boolean,
  emptyText: { type: String, default: '暂无数据' },
})

const showLoading = ref(false)
let loadingTimer = null

function syncLoading(value) {
  window.clearTimeout(loadingTimer)
  showLoading.value = false
  if (value) loadingTimer = window.setTimeout(() => { showLoading.value = true }, 300)
}

watch(() => props.loading, syncLoading, { immediate: true })
onBeforeUnmount(() => window.clearTimeout(loadingTimer))
</script>

<template>
  <div v-if="loading && !showLoading" class="shared-loading shared-loading--delay" aria-hidden="true" />
  <div v-else-if="loading" class="shared-loading" role="status" aria-live="polite">
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
