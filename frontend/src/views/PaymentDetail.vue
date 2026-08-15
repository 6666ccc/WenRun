<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getCharge, payCharge } from '../api'
import { PAY_STATUS_MAP, PAY_TYPE_MAP, formatDateTime, formatMoney } from '../utils'
import AppShell from '../components/AppShell.vue'
import StatusBadge from '../components/StatusBadge.vue'
import UiState from '../components/UiState.vue'

const route = useRoute()
const router = useRouter()
const charge = ref(null)
const loading = ref(true)
const error = ref('')
const paying = ref(false)
const payType = ref(2)
const message = ref('')
async function load() {
  try { charge.value = await getCharge(Number(route.params.id)) }
  catch (nextError) { error.value = nextError.message || '加载失败' }
  finally { loading.value = false }
}
onMounted(load)
async function pay() {
  paying.value = true
  message.value = ''
  try {
    await payCharge(Number(route.params.id), { payType: payType.value, paidAmount: charge.value.totalAmount })
    message.value = '支付成功！'
    await load()
  } catch (nextError) { message.value = nextError.message || '支付失败' }
  finally { paying.value = false }
}
</script>

<template>
  <AppShell>
    <button class="view-back" @click="router.push('/payment')">‹ 返回缴费列表</button>
    <UiState :loading="loading" :error="error" :empty="!charge" empty-text="收费单不存在">
      <div class="vue-detail">
        <section class="card">
          <div class="flex-between mb-md"><h2>收费详情</h2><StatusBadge :status="charge.payStatus" :map="PAY_STATUS_MAP" /></div>
          <div class="vue-detail-grid">
            <div><small>订单编号</small><strong>{{ charge.orderNo }}</strong></div><div><small>患者</small><strong>{{ charge.patientName }}</strong></div>
            <div><small>创建时间</small><strong>{{ formatDateTime(charge.createTime) }}</strong></div><div><small>支付时间</small><strong>{{ charge.payTime ? formatDateTime(charge.payTime) : '—' }}</strong></div>
            <div><small>总金额</small><strong class="amount">{{ formatMoney(charge.totalAmount) }}</strong></div><div><small>支付方式</small><strong>{{ PAY_TYPE_MAP[charge.payType] || '—' }}</strong></div>
          </div>
        </section>
        <section class="card">
          <h3>费用明细</h3>
          <div class="view-table-wrap"><table class="view-table"><thead><tr><th>项目</th><th>金额</th></tr></thead><tbody><tr v-for="detail in charge.details" :key="detail.id"><td>{{ detail.itemName }}</td><td>{{ formatMoney(detail.amount) }}</td></tr></tbody></table></div>
          <div class="vue-total"><strong>合计</strong><b>{{ formatMoney(charge.totalAmount) }}</b></div>
        </section>
        <section v-if="charge.payStatus === 0" class="card card--accent-top">
          <h3>选择支付方式</h3>
          <div class="vue-methods"><button v-for="(label,key) in PAY_TYPE_MAP" :key="key" class="view-pay-method" :class="{ 'view-pay-method--active': Number(key) === payType }" @click="payType=Number(key)">{{ label }}</button></div>
          <div v-if="message" class="vue-message" :class="{ success: message.includes('成功') }">{{ message }}</div>
          <button class="btn btn--accent btn--lg full" :disabled="paying || message.includes('成功')" @click="pay">{{ paying ? '支付中…' : `确认支付 ${formatMoney(charge.totalAmount)}` }}</button>
        </section>
      </div>
    </UiState>
  </AppShell>
</template>

<style scoped>
.vue-detail{display:flex;flex-direction:column;gap:16px;max-width:680px}.vue-detail h2,.vue-detail h3{margin:0 0 12px}.vue-detail-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px 24px}.vue-detail-grid small,.vue-detail-grid strong{display:block}.vue-detail-grid small{color:var(--c-muted)}.amount,.vue-total b{color:var(--c-accent);font-size:1.2rem}.vue-total{display:flex;justify-content:space-between;border-top:2px solid var(--c-border);padding-top:12px}.vue-methods{display:flex;gap:10px;margin-bottom:20px}.vue-message{padding:8px 14px;color:var(--c-danger);background:var(--c-danger-bg);border-radius:var(--radius);margin-bottom:16px}.vue-message.success{color:var(--c-success);background:var(--c-success-bg)}.full{width:100%}
</style>
