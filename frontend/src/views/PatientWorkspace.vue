<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useIsPc } from '../composables/useIsPc'
import { WORKSPACE_TITLES, workspacePanelFor } from '../features/experience/workspace'
import Assistant from './Assistant.vue'
import Registration from './Registration.vue'
import RegistrationDetail from './RegistrationDetail.vue'
import SideDrawer from '../components/SideDrawer.vue'
import RegistrationBooking from '../components/workspace/RegistrationBooking.vue'
import RegistrationRecord from '../components/workspace/RegistrationRecord.vue'

const route = useRoute()
const router = useRouter()
const isPc = useIsPc()

const panel = computed(() => workspacePanelFor(route.path, route.params))
const panelTitle = computed(() => (panel.value ? WORKSPACE_TITLES[panel.value.kind] : ''))
const mobileView = computed(() => {
  if (!panel.value) return Assistant
  if (panel.value.kind === 'registration') return Registration
  return RegistrationDetail
})
const archiveRecords = { path: '/archive', query: { tab: 'registrations' } }

/** 关闭抽屉：来自首页就后退（浏览器后退 = 关闭），否则直接回首页且不留历史。 */
function closePanel() {
  const back = window.history.state?.back
  if (typeof back === 'string' && back.startsWith('/home')) router.back()
  else router.replace('/home')
}
</script>

<template>
  <template v-if="isPc">
    <Assistant />
    <SideDrawer
      :open="Boolean(panel)"
      :title="panelTitle"
      :back-label="panel?.kind === 'record' ? '个人档案' : ''"
      @close="closePanel"
      @back="router.push(archiveRecords)"
    >
      <RegistrationBooking v-if="panel?.kind === 'registration'" />
      <RegistrationRecord
        v-else-if="panel?.kind === 'record'"
        :id="panel.id"
        :show-back="false"
        @cancelled="router.replace(archiveRecords)"
      />
    </SideDrawer>
  </template>
  <component :is="mobileView" v-else />
</template>
