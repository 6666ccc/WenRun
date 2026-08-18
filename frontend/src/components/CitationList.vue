<script setup>
import { sourceExcerpt, sourceLabel, sourceLocation } from '../features/assistant/citation.js'

defineProps({
  sources: { type: Array, default: () => [] },
})
</script>

<template>
  <details v-if="sources.length" class="chat-citations">
    <summary>查看依据（{{ sources.length }}）</summary>
    <ul>
    <li v-for="(source, index) in sources" :key="source.id || index">
      <strong>{{ sourceLabel(source) }}</strong>
      <small v-if="sourceLocation(source)">{{ sourceLocation(source) }}</small>
      <p v-if="sourceExcerpt(source)">{{ sourceExcerpt(source) }}</p>
    </li>
    </ul>
  </details>
</template>
