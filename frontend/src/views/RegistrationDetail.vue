<script setup>
import { useRoute, useRouter } from 'vue-router'
import AppShell from '../components/AppShell.vue'
import RegistrationRecord from '../components/workspace/RegistrationRecord.vue'

const route = useRoute()
const router = useRouter()
</script>

<template>
  <AppShell>
    <RegistrationRecord :id="String(route.params.id)" @back="router.push('/user')" @cancelled="router.replace('/user')" />
  </AppShell>
</template>
