<script setup>
import UiIcon from '../UiIcon.vue'

defineEmits(['unavailable'])

const docs = [
  { icon: 'record', label: '病历', tone: 'blue' },
  { icon: 'clipboard', label: '报告单', tone: 'green' },
  { icon: 'pill', label: '药物', tone: 'violet' },
  { icon: 'shield', label: '体检报告', tone: 'amber' },
]
</script>

<template>
  <section class="archive-panel">
    <header>
      <h2>就医资料</h2>
      <button class="archive-link" type="button" @click="$emit('unavailable', '就医资料')">上传资料 ›</button>
    </header>
    <div class="doc-grid">
      <button v-for="item in docs" :key="item.label" :class="['doc-card', `is-${item.tone}`]" type="button" @click="$emit('unavailable', item.label)">
        <span><UiIcon :name="item.icon" :size="18" /></span>
        <strong>{{ item.label }}</strong>
        <small>共 0 份 · 数据库还未设计</small>
      </button>
    </div>
  </section>
</template>
