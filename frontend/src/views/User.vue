<script setup>
import AppShell from '../components/AppShell.vue'
import PageHeader from '../components/PageHeader.vue'
import UserProfile from '../components/workspace/UserProfile.vue'
</script>

<template>
  <AppShell>
    <PageHeader title="个人中心" subtitle="管理您的个人档案、健康档案与挂号记录" />
    <UserProfile />
  </AppShell>
</template>
