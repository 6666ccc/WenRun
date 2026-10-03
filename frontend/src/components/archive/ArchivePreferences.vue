<script setup>
import { ref, watch } from 'vue'
import { listPreferences, updatePreference } from '../../api/modules/preferences'

const props = defineProps({ patientId: { type: [Number, String], default: null } })
const items = ref([])
const loading = ref(false)
const error = ref('')
const notice = ref('')
const target = ref(null)
const content = ref('')
const days = ref('')
const review = ref(null)
const saving = ref(false)
let generation = 0
const labels = { communication_preference: '沟通偏好', appointment_preference: '挂号偏好', accessibility_need: '无障碍需求' }

async function load() {
  const epoch = ++generation
  target.value = review.value = null
  items.value = []
  error.value = ''
  notice.value = ''
  loading.value = true
  try {
    if (!props.patientId) return
    let page = 0
    while (true) {
      const rows = await listPreferences(props.patientId, page++)
      if (epoch !== generation) return
      items.value.push(...rows.filter((item) => ['active', 'pending'].includes(item.status)))
      if (rows.length < 50) break
    }
  } catch (err) {
    if (epoch === generation) error.value = err.message
  } finally {
    if (epoch === generation) loading.value = false
  }
}
watch(() => props.patientId, load, { immediate: true })

function edit(item) {
  target.value = { ...item }
  content.value = item.content
  days.value = ''
  review.value = null
  error.value = ''
}
function prepare() {
  if (!content.value.trim()) return
  const expireTime = days.value ? new Date(Date.now() + Number(days.value) * 86400000)
    .toLocaleString('sv-SE', { timeZone: 'Asia/Shanghai' }).replace(' ', 'T') : target.value.expireTime || null
  review.value = { patientId: props.patientId, target: { ...target.value },
    body: { type: target.value.type, content: content.value.trim(),
      expectedVersion: target.value.version, expireTime } }
}
async function save() {
  if (saving.value || !review.value) return
  const snapshot = review.value
  const epoch = generation
  saving.value = true
  error.value = ''
  try {
    await updatePreference(snapshot.patientId, snapshot.target.memoryId, snapshot.body)
    if (epoch === generation) {
      await load()
      if (props.patientId === snapshot.patientId) notice.value = '偏好已保存。'
    }
  } catch (err) {
    if (epoch === generation) {
      // A stale version must be reloaded and shown again before a subsequent save.
      await load()
      if (props.patientId === snapshot.patientId) error.value = `${err.message}；请根据当前记录重新编辑并确认。`
    }
  } finally { saving.value = false }
}
</script>

<template>
  <section class="preferences" aria-labelledby="preferences-title" :aria-busy="loading">
    <h2 id="preferences-title">已保存偏好</h2>
    <p class="preferences__note">沟通、挂号与无障碍偏好由当前患者共享。身体数据请在上方健康数据中更新。</p>
    <p v-if="error" role="alert">{{ error }}</p>
    <p v-if="notice" role="status">{{ notice }}</p>
    <p v-if="loading" role="status">正在读取偏好…</p>
    <p v-else-if="!items.length">暂无已保存偏好。在助手中明确说“记住”后，可确认保存。</p>
    <ul v-else>
      <li v-for="item in items" :key="item.memoryId">
        <div><strong>{{ labels[item.type] || '偏好' }}</strong><p>{{ item.content }}</p>
          <small>有效期：{{ item.expireTime || '长期有效' }} · 来源会话：{{ item.sourceConversationId || '未标注' }}</small>
        </div>
        <button type="button" :disabled="saving" @click="edit(item)">编辑</button>
      </li>
    </ul>
    <form v-if="target && !review" @submit.prevent="prepare">
      <label>偏好内容<textarea v-model="content" required maxlength="500" rows="3" /></label>
      <label>有效天数（留空保留现有有效期）<input v-model="days" type="number" min="1" max="365" step="1"></label>
      <button type="button" @click="target = null">取消</button>
      <button type="submit">查看确认内容</button>
    </form>
    <div v-if="review" class="preferences__review" aria-live="polite">
      <p>患者档案编号：{{ review.patientId }}</p>
      <p>旧值：{{ review.target.content }}</p><p>新值：{{ review.body.content }}</p>
      <p>有效期：{{ review.body.expireTime || '长期有效' }}</p>
      <button type="button" :disabled="saving" @click="review = null">返回编辑</button>
      <button type="button" :disabled="saving" @click="save">{{ saving ? '保存中…' : '确认保存' }}</button>
    </div>
  </section>
</template>

<style scoped>
.preferences { margin-top: 24px; padding: 24px; background: var(--surface, #fff); border: 1px solid var(--border, #e1e6e3); border-radius: 16px; }
h2 { font-size: 18px; margin: 0 0 8px; }
.preferences__note, small { color: var(--text-secondary, #59675f); line-height: 1.6; }
ul { list-style: none; padding: 0; }
li { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 16px 0; border-bottom: 1px solid var(--border, #e1e6e3); }
li p { white-space: pre-wrap; overflow-wrap: anywhere; }
button { flex-shrink: 0; white-space: nowrap; min-height: 44px; padding: 8px 14px; border: 1px solid var(--border, #d3ded7); border-radius: 8px; color: inherit; background: transparent; cursor: pointer; }
button:disabled { opacity: .6; cursor: default; }
button:focus-visible, textarea:focus-visible, input:focus-visible { outline: 2px solid var(--primary, #328665); outline-offset: 3px; }
label { display: grid; gap: 8px; margin: 14px 0; }
textarea, input { width: 100%; box-sizing: border-box; padding: 12px; border: 1px solid var(--border, #d3ded7); border-radius: 8px; font: inherit; background: transparent; color: inherit; }
.preferences__review { margin-top: 16px; padding: 16px; border: 1px solid var(--border, #e1e6e3); border-radius: 12px; overflow-wrap: anywhere; }
form button, .preferences__review button { margin-right: 8px; }
</style>
