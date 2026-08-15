<script setup>
defineProps({ title: String, subtitle: String })
</script>

<template>
  <div class="view-page-header flex-between">
    <div>
      <h1>{{ title }}</h1>
      <p v-if="subtitle" class="view-page-header__sub">{{ subtitle }}</p>
    </div>
    <slot />
  </div>
</template>
