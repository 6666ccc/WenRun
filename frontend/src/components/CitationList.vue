<script setup>
import { sourceExcerpt, sourceLabel, sourceLocation } from '../features/assistant/citation.js'

defineProps({
  sources: { type: Array, default: () => [] },
})
</script>

<template>
  <ul v-if="sources.length" class="agent-citations">
    <li v-for="(source, index) in sources" :key="source.id || index" class="agent-citations__item">
      <strong>{{ sourceLabel(source) }}</strong>
      <small v-if="sourceLocation(source)">{{ sourceLocation(source) }}</small>
      <p v-if="sourceExcerpt(source)">{{ sourceExcerpt(source) }}</p>
    </li>
  </ul>
</template>
