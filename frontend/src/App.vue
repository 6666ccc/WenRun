<template>
  <RouterView v-slot="{ Component, route }">
    <Transition name="clinical-route" mode="out-in">
      <div
        :key="route.meta.patient && route.path !== '/archive' ? 'patient-workspace' : route.path"
        class="app-route"
      >
        <component :is="Component" />
      </div>
    </Transition>
  </RouterView>
</template>

<script setup>
import { RouterView } from 'vue-router'
</script>

<style>
.app-route { min-height: 100%; }
</style>
