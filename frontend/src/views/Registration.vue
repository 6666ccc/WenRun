<script setup>
import AppShell from '../components/AppShell.vue'
import PageHeader from '../components/PageHeader.vue'
import RegistrationBooking from '../components/workspace/RegistrationBooking.vue'
</script>

<template>
  <AppShell>
    <PageHeader title="预约挂号" subtitle="筛选可预约号源，选择合适的医生与时段" />
    <RegistrationBooking />
  </AppShell>
</template>
