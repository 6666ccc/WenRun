<script setup>
defineProps({ title: String, subtitle: String })
</script>

<template>
  <header class="view-page-header">
    <div>
      <h1>{{ title }}</h1>
      <p v-if="subtitle" class="view-page-header__sub">{{ subtitle }}</p>
    </div>
    <div v-if="$slots.default" class="view-page-header__actions"><slot /></div>
  </header>
</template>
