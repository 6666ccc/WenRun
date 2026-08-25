<script setup>
import { computed, onMounted, ref } from 'vue'
import { listDepts, listStaff } from '../api'
import AppShell from '../components/AppShell.vue'
import PageHeader from '../components/PageHeader.vue'
import UiIcon from '../components/UiIcon.vue'
import UiState from '../components/UiState.vue'

const depts = ref([])
const staff = ref([])
const loading = ref(true)
const staffLoading = ref(false)
const staffError = ref('')
const error = ref('')
const selected = ref(null)
const search = ref('')
const filtered = computed(() => depts.value.filter((dept) => dept.status === 1 && (!search.value || dept.deptName.includes(search.value) || dept.deptCode.includes(search.value))))

onMounted(async () => {
  try { depts.value = await listDepts({ status: 1 }) || [] }
  catch (nextError) { error.value = nextError.message || '加载失败' }
  finally { loading.value = false }
})

async function selectDept(dept) {
  if (selected.value?.id === dept.id) { selected.value = null; staff.value = []; return }
  selected.value = dept
  staffError.value = ''
  staffLoading.value = true
  try { staff.value = await listStaff({ deptId: dept.id, status: 1 }) || [] }
  catch (nextError) { staff.value = []; staffError.value = nextError.message || '医生信息暂时无法获取' }
  finally { staffLoading.value = false }
}
</script>

<template>
  <AppShell>
    <PageHeader title="科室浏览" subtitle="浏览诊所各科室信息及医生团队" />
    <div v-if="!loading && depts.length" class="view-search"><UiIcon name="search" :size="18" /><input v-model="search" class="input" placeholder="搜索科室名称或编码…" aria-label="搜索科室名称或编码"></div>
    <UiState :loading="loading" :error="error" :empty="!filtered.length" :empty-text="search ? '未找到匹配的科室' : '暂无科室数据'">
      <div class="vue-dept-grid stagger">
        <article v-for="dept in filtered" :key="dept.id" class="vue-dept-item">
          <button type="button" class="card view-dept-card" :class="{ 'view-dept-card--active card--accent-top': selected?.id === dept.id }" :aria-expanded="selected?.id === dept.id" :aria-controls="`dept-staff-${dept.id}`" @click="selectDept(dept)">
            <span><h3>{{ dept.deptName }}</h3><p class="text-muted text-sm">{{ dept.deptCode }}</p></span><UiIcon name="arrowRight" :size="18" />
          </button>
          <div v-if="selected?.id === dept.id" :id="`dept-staff-${dept.id}`" class="vue-staff" role="region" :aria-label="`${dept.deptName}医生团队`">
            <div v-if="staffLoading" class="shared-loading"><div class="shared-loading__spinner" /></div>
            <p v-else-if="staffError" class="vue-staff__error" role="alert">{{ staffError }}</p>
            <p v-else-if="!staff.length" class="text-muted text-sm">该科室当前没有可展示的医生</p>
            <div v-else v-for="doctor in staff" :key="doctor.id"><strong>{{ doctor.name }}</strong><span>{{ doctor.title }} · {{ doctor.staffNo }}</span></div>
          </div>
        </article>
      </div>
    </UiState>
  </AppShell>
</template>

<style scoped>
.vue-dept-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:16px;align-items:start}.vue-dept-item{min-width:0}.view-dept-card{display:flex;align-items:center;justify-content:space-between;gap:16px;width:100%;font:inherit;color:inherit;text-align:left;cursor:pointer}.view-dept-card h3{font-family:var(--font-sans);margin:0 0 4px}.view-dept-card>svg{flex:0 0 auto;color:var(--color-brand-700);transition:transform var(--motion-fast)}.view-dept-card[aria-expanded="true"]>svg{transform:rotate(90deg)}.vue-staff{margin-top:8px;padding:14px;display:flex;gap:8px;flex-wrap:wrap;border:1px solid var(--color-border);border-radius:var(--radius);background:var(--color-surface)}.vue-staff>div{padding:9px 14px;background:var(--c-bg);border:1px solid var(--c-border-light);border-radius:var(--radius)}.vue-staff strong,.vue-staff span{display:block}.vue-staff span{font-size:.8rem;color:var(--c-sub)}.vue-staff__error{margin:0;color:var(--color-danger);font-size:13px}
@media(max-width:1023px){.vue-dept-grid{display:flex;flex-direction:column;gap:12px}.vue-staff{flex-direction:column}}
</style>
