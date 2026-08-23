<script setup>
import { computed, onMounted, ref } from 'vue'
import { useAuth } from '../stores'
import { listCharges } from '../api'
import { PAY_STATUS_MAP, formatDateTime, formatMoney } from '../utils'
import AppShell from '../components/AppShell.vue'
import PageHeader from '../components/PageHeader.vue'
import StatusBadge from '../components/StatusBadge.vue'
import UiState from '../components/UiState.vue'

const { user } = useAuth()
const charges = ref([])
const loading = ref(true)
const error = ref('')
const pending = computed(() => charges.value.filter((item) => item.payStatus === 0))
const paid = computed(() => charges.value.filter((item) => item.payStatus !== 0))
const pendingTotal = computed(() => pending.value.reduce((sum, item) => sum + Number(item.totalAmount || 0), 0))

onMounted(async () => {
  if (!user.value?.patientId) return void (loading.value = false)
  try { charges.value = await listCharges({ patientId: user.value.patientId }) || [] }
  catch (nextError) { error.value = nextError.message || '加载失败' }
  finally { loading.value = false }
})
</script>

<template>
  <AppShell>
    <PageHeader title="门诊缴费" subtitle="查看待缴费项目和缴费记录" />
    <UiState :loading="loading" :error="error" :empty="!charges.length" empty-text="暂无缴费记录">
      <div class="view-pay-summary">
        <div class="view-pay-summary__item view-pay-summary__item--accent"><div class="view-pay-summary__label">待缴费</div><div class="view-pay-summary__value accent">{{ pending.length }}</div></div>
        <div class="view-pay-summary__item"><div class="view-pay-summary__label">待缴金额</div><div class="view-pay-summary__value">{{ formatMoney(pendingTotal) }}</div></div>
        <div class="view-pay-summary__item"><div class="view-pay-summary__label">已缴费</div><div class="view-pay-summary__value success">{{ paid.length }}</div></div>
      </div>
      <section v-if="pending.length" class="clinic-panel vue-pay-section">
        <div class="clinic-panel__head"><h2>待缴费 ({{ pending.length }})</h2></div>
        <div class="clinic-panel__body">
        <div class="vue-pay-grid">
          <article v-for="charge in pending" :key="charge.id" class="card card--accent-top">
            <div class="flex-between mb-sm"><strong>{{ charge.orderNo }}</strong><b class="accent">{{ formatMoney(charge.totalAmount) }}</b></div>
            <p class="text-sub text-sm">{{ formatDateTime(charge.createTime) }}</p>
            <div class="vue-tags"><span v-for="detail in charge.details" :key="detail.id">{{ detail.itemName }} {{ formatMoney(detail.amount) }}</span></div>
            <RouterLink :to="`/payment/${charge.id}`" class="btn btn--primary btn--sm">去支付</RouterLink>
          </article>
        </div>
        </div>
      </section>
      <section v-if="paid.length" class="clinic-panel vue-pay-section">
        <div class="clinic-panel__head"><h2>已缴费 ({{ paid.length }})</h2></div>
        <div class="clinic-panel__body">
        <div class="vue-pay-grid">
          <article v-for="charge in paid" :key="charge.id" class="card">
            <div class="flex-between mb-sm"><strong>{{ charge.orderNo }}</strong><StatusBadge :status="charge.payStatus" :map="PAY_STATUS_MAP" /></div>
            <p class="text-sub text-sm">金额：{{ formatMoney(charge.totalAmount) }}</p><p class="text-sub text-sm">时间：{{ formatDateTime(charge.payTime || charge.createTime) }}</p>
          </article>
        </div>
        </div>
      </section>
    </UiState>
  </AppShell>
</template>

<style scoped>
.accent{color:var(--color-brand-700)}.success{color:var(--c-success)}.vue-pay-section{margin-top:24px}.vue-pay-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:16px}.vue-tags{display:flex;flex-wrap:wrap;gap:4px;margin:10px 0}.vue-tags span{padding:2px 8px;border:1px solid var(--color-border-strong);border-radius:99px;background:var(--color-chip-bg);font-size:.75rem;color:var(--color-brand-800)}
@media(max-width:700px){.vue-pay-grid{grid-template-columns:1fr}}
</style>
