<script setup>
import { computed } from 'vue'
import { REG_STATUS_MAP, formatVisitSchedule } from '../../utils'
import StatusBadge from '../StatusBadge.vue'

const props = defineProps({
  registrations: { type: Array, default: () => [] },
  error: { type: String, default: '' },
})
const emit = defineEmits(['cancel'])
const pending = computed(() => props.registrations.filter((item) => item.status === 1))
const history = computed(() => props.registrations.filter((item) => item.status !== 1))
</script>

<template>
  <section class="archive-panel">
    <header>
      <div>
        <h2>我的挂号</h2>
        <p>待就诊与历史挂号统一在此管理</p>
      </div>
      <span class="archive-panel__count">{{ pending.length }} 项待就诊</span>
    </header>
    <p v-if="error" class="archive-panel__error" role="alert">{{ error }}</p>
    <div v-else-if="registrations.length" class="archive-regs">
      <article v-for="item in registrations" :key="item.id">
        <div>
          <strong>{{ item.deptName }} · {{ item.staffName }}</strong>
          <span>{{ formatVisitSchedule(item.workDate, item.timePeriod) }}</span>
          <small>挂号单 {{ item.regNo }}</small>
        </div>
        <StatusBadge :status="item.status" :map="REG_STATUS_MAP" />
        <div class="archive-regs__actions">
          <RouterLink class="btn btn--outline btn--sm" :to="`/registration/${item.id}`">详情</RouterLink>
          <button v-if="item.status === 1" class="btn btn--danger btn--sm" type="button" @click="emit('cancel', item)">取消</button>
        </div>
      </article>
    </div>
    <div v-else class="archive-empty">
      <strong>还没有挂号记录</strong>
      <p>预约成功后，记录会显示在这里。</p>
      <RouterLink class="btn btn--primary btn--sm" to="/registration">去预约挂号</RouterLink>
    </div>
    <p v-if="history.length" class="archive-panel__hint">含 {{ history.length }} 条历史记录</p>
  </section>
</template>
