<script setup>
defineProps({
  title: { type: String, default: '' },
  hint: { type: String, default: '该模块的表结构尚未建立，当前仅作界面预览。' },
})
</script>

<template>
  <section class="archive-unavailable">
    <h3 v-if="title">{{ title }}</h3>
    <p>数据库还未设计</p>
    <small>{{ hint }}</small>
  </section>
</template>

<style scoped>
.archive-unavailable {
  display: grid;
  gap: 8px;
  padding: 28px 24px;
  border: 1px dashed var(--color-border-strong);
  border-radius: 18px;
  background: var(--color-warning-bg);
  color: var(--color-warning);
}
.archive-unavailable h3 { margin: 0; color: var(--color-text); font-size: 16px; }
.archive-unavailable p { margin: 0; font-size: 15px; font-weight: 700; }
.archive-unavailable small { color: var(--color-text-secondary); font-size: 13px; }
</style>
