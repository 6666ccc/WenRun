<script setup>
import { reactive, watch } from 'vue'

const props = defineProps({
  health: { type: Object, default: null },
  saving: Boolean,
  error: { type: String, default: '' },
  message: { type: String, default: '' },
})
const emit = defineEmits(['save', 'cancel'])
const form = reactive({ pastHistory: '', familyHistory: '', personalHistory: '' })

watch(() => props.health, (data) => {
  Object.assign(form, {
    pastHistory: data?.pastHistory || '',
    familyHistory: data?.familyHistory || '',
    personalHistory: data?.personalHistory || '',
  })
}, { immediate: true })
</script>

<template>
  <form class="archive-form" @submit.prevent="emit('save', { ...form })">
    <h3>健康信息</h3>
    <p v-if="error" class="archive-panel__error" role="alert">{{ error }}</p>
    <p v-else-if="message" class="archive-panel__msg" role="status">{{ message }}</p>
    <template v-if="!error">
      <label>既往史<textarea v-model="form.pastHistory" class="input" rows="4" maxlength="2000" placeholder="例如：高血压 5 年，阑尾切除术后"></textarea></label>
      <label>家族史<textarea v-model="form.familyHistory" class="input" rows="4" maxlength="2000" placeholder="例如：父亲高血压，母亲 2 型糖尿病"></textarea></label>
      <label>个人史<textarea v-model="form.personalHistory" class="input" rows="4" maxlength="2000" placeholder="例如：偶尔饮酒，不吸烟"></textarea></label>
      <div class="archive-dialog__actions">
        <button class="btn btn--ghost" type="button" @click="emit('cancel')">取消</button>
        <button class="btn btn--primary" type="submit" :disabled="saving">{{ saving ? '保存中…' : '保存健康信息' }}</button>
      </div>
    </template>
  </form>
</template>
