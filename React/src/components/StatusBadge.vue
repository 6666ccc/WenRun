<script setup>
import { computed } from 'vue'
const props = defineProps({ status: [String, Number], map: Object, fallback: { type: String, default: '未知' } })
const info = computed(() => props.map?.[props.status])
</script>

<template>
  <span class="shared-status" :class="info?.cls || 'shared-status--cancelled'">
    {{ info?.label || fallback }}
  </span>
</template>
