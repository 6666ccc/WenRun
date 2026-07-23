<script setup>
defineProps({ show: Boolean, title: String, message: String, loading: Boolean })
defineEmits(['confirm', 'cancel'])
</script>

<template>
  <div v-if="show" class="shared-dialog-overlay" @click="$emit('cancel')">
    <div class="shared-dialog" @click.stop>
      <h3>{{ title || '确认操作' }}</h3>
      <p>{{ message }}</p>
      <div class="shared-dialog__actions">
        <button class="btn btn--ghost" :disabled="loading" @click="$emit('cancel')">取消</button>
        <button class="btn btn--primary" :disabled="loading" @click="$emit('confirm')">
          {{ loading ? '处理中…' : '确认' }}
        </button>
      </div>
    </div>
  </div>
</template>
