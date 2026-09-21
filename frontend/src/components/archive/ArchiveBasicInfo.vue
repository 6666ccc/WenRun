<script setup>
import { reactive, watch } from 'vue'

const props = defineProps({
  patient: { type: Object, required: true },
  saving: Boolean,
  message: { type: String, default: '' },
})
const emit = defineEmits(['save', 'cancel'])
const form = reactive({
  name: '', gender: '', phone: '', idCard: '', birthDate: '', address: '', allergyHistory: '',
})

watch(() => props.patient, (data) => {
  Object.assign(form, {
    name: data.name || '',
    gender: data.gender ?? '',
    phone: data.phone || '',
    idCard: data.idCard || '',
    birthDate: data.birthDate || '',
    address: data.address || '',
    allergyHistory: data.allergyHistory || '',
  })
}, { immediate: true })

const fields = [
  { label: '姓名', key: 'name', autocomplete: 'name' },
  { label: '手机号', key: 'phone', type: 'tel', autocomplete: 'tel' },
  { label: '身份证号', key: 'idCard', autocomplete: 'off' },
  { label: '出生日期', key: 'birthDate', type: 'date' },
  { label: '地址', key: 'address', autocomplete: 'street-address' },
  { label: '过敏史', key: 'allergyHistory' },
]
</script>

<template>
  <form class="archive-form" @submit.prevent="emit('save', { ...form })">
    <h3>基本资料</h3>
    <p v-if="message" class="archive-panel__msg" role="status">{{ message }}</p>
    <div class="archive-form__grid">
      <label v-for="field in fields" :key="field.key">
        {{ field.label }}
        <input v-model="form[field.key]" class="input" :type="field.type || 'text'" :autocomplete="field.autocomplete">
      </label>
      <label>
        性别
        <select v-model="form.gender" class="input">
          <option value="">请选择</option>
          <option :value="0">女</option>
          <option :value="1">男</option>
        </select>
      </label>
    </div>
    <div class="archive-dialog__actions">
      <button class="btn btn--ghost" type="button" @click="emit('cancel')">取消</button>
      <button class="btn btn--primary" type="submit" :disabled="saving">{{ saving ? '保存中…' : '保存资料' }}</button>
    </div>
  </form>
</template>
