<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import {
  createExercise,
  createSleepRecord,
  deleteExercise,
  deleteSleepRecord,
  getActivitySummary,
  listExercises,
  listSleepRecords,
  updateExercise,
  updateSleepRecord,
} from '../../api'
import { formatDateTime } from '../../utils'
import {
  EXERCISE_INTENSITIES,
  EXERCISE_TYPES,
  SLEEP_QUALITIES,
  emptyExerciseForm,
  emptySleepForm,
  fillExerciseForm,
  fillSleepForm,
  formatDurationMinutes,
  sleepDurationMinutes,
  toExercisePayload,
  toSleepPayload,
} from '../../utils/activity'
import UiIcon from '../UiIcon.vue'

const props = defineProps({
  patientId: { type: [Number, String], default: null },
})

const range = ref(7)
const summary = ref(null)
const exercises = ref([])
const sleeps = ref([])
const loading = ref(false)
const error = ref('')
const message = ref('')
const saving = ref(false)
const editor = ref('')
const editingId = ref(null)
const exerciseForm = reactive(emptyExerciseForm())
const sleepForm = reactive(emptySleepForm())

const previewSleep = computed(() => formatDurationMinutes(sleepDurationMinutes(sleepForm.bedtime, sleepForm.wakeTime)))
const exerciseMinutes = computed(() => formatDurationMinutes(summary.value?.exerciseMinutes ?? 0))
const sleepAverage = computed(() => formatDurationMinutes(summary.value?.sleepAvgMinutes))

function resetExerciseForm(record) {
  Object.assign(exerciseForm, record ? fillExerciseForm(record) : emptyExerciseForm())
}

function resetSleepForm(record) {
  Object.assign(sleepForm, record ? fillSleepForm(record) : emptySleepForm())
}

function openExercise(record) {
  message.value = ''
  editingId.value = record?.id || null
  resetExerciseForm(record)
  if (!record && !exerciseForm.startedAt) {
    exerciseForm.startedAt = nowLocal()
  }
  editor.value = 'exercise'
}

function openSleep(record) {
  message.value = ''
  editingId.value = record?.id || null
  resetSleepForm(record)
  editor.value = 'sleep'
}

function closeEditor() {
  editor.value = ''
  editingId.value = null
}

function nowLocal() {
  const now = new Date()
  const pad = (n) => String(n).padStart(2, '0')
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}T${pad(now.getHours())}:${pad(now.getMinutes())}`
}

async function load() {
  if (!props.patientId) return
  loading.value = true
  error.value = ''
  try {
    const [nextSummary, nextExercises, nextSleeps] = await Promise.all([
      getActivitySummary(props.patientId, range.value),
      listExercises(props.patientId),
      listSleepRecords(props.patientId),
    ])
    summary.value = nextSummary
    exercises.value = nextExercises || []
    sleeps.value = nextSleeps || []
  } catch (nextError) {
    error.value = nextError.message || '运动睡眠数据加载失败'
  } finally {
    loading.value = false
  }
}

async function saveExercise() {
  saving.value = true
  message.value = ''
  try {
    const payload = toExercisePayload(exerciseForm)
    if (editingId.value) await updateExercise(props.patientId, editingId.value, payload)
    else await createExercise(props.patientId, payload)
    closeEditor()
    await load()
  } catch (nextError) {
    message.value = nextError.message || '运动记录保存失败'
  } finally {
    saving.value = false
  }
}

async function saveSleep() {
  saving.value = true
  message.value = ''
  try {
    const payload = toSleepPayload(sleepForm)
    if (editingId.value) await updateSleepRecord(props.patientId, editingId.value, payload)
    else await createSleepRecord(props.patientId, payload)
    closeEditor()
    await load()
  } catch (nextError) {
    message.value = nextError.message || '睡眠记录保存失败'
  } finally {
    saving.value = false
  }
}

async function removeExercise(item) {
  if (!window.confirm(`删除这条${item.exerciseName || '运动'}记录？`)) return
  try {
    await deleteExercise(props.patientId, item.id)
    await load()
  } catch (nextError) {
    error.value = nextError.message || '删除运动记录失败'
  }
}

async function removeSleep(item) {
  if (!window.confirm('删除这条睡眠记录？')) return
  try {
    await deleteSleepRecord(props.patientId, item.id)
    await load()
  } catch (nextError) {
    error.value = nextError.message || '删除睡眠记录失败'
  }
}

function exerciseMeta(item) {
  const parts = []
  if (item.distanceKm != null) parts.push(`${item.distanceKm} 公里`)
  if (item.caloriesKcal != null) parts.push(`${item.caloriesKcal} 千卡`)
  if (item.intensityName) parts.push(item.intensityName)
  return parts.join(' · ')
}

watch(() => props.patientId, load)
watch(range, load)
onMounted(load)
</script>

<template>
  <div class="activity">
    <p v-if="error" class="archive-panel__error" role="alert">{{ error }}</p>

    <section class="archive-panel activity__summary">
      <header>
        <div>
          <div>
            <h2>运动与睡眠</h2>
            <p>手动记录。设备同步尚未开放。</p>
          </div>
        </div>
        <div class="activity__ranges" role="group" aria-label="汇总范围">
          <button type="button" :class="{ 'is-active': range === 7 }" @click="range = 7">近 7 天</button>
          <button type="button" :class="{ 'is-active': range === 30 }" @click="range = 30">近 30 天</button>
        </div>
      </header>
      <div class="metric-grid">
        <article class="metric-card">
          <div class="metric-card__head">
            <span class="metric-card__icon"><UiIcon name="activity" :size="16" /></span>
            <span class="metric-card__label">运动时长</span>
          </div>
          <strong>{{ loading && !summary ? '—' : exerciseMinutes }}</strong>
          <span class="metric-card__foot">{{ summary?.exerciseCount ?? 0 }} 次记录</span>
        </article>
        <article class="metric-card">
          <div class="metric-card__head">
            <span class="metric-card__icon"><UiIcon name="zap" :size="16" /></span>
            <span class="metric-card__label">消耗热量</span>
          </div>
          <strong>{{ summary?.exerciseCalories ?? '—' }}<small v-if="summary?.exerciseCalories != null">千卡</small></strong>
          <span class="metric-card__foot">仅统计填写了热量的记录</span>
        </article>
        <article class="metric-card metric-card--featured">
          <div class="metric-card__head">
            <span class="metric-card__icon"><UiIcon name="heart" :size="16" /></span>
            <span class="metric-card__label">平均睡眠</span>
          </div>
          <strong>{{ sleepAverage }}</strong>
          <span class="metric-card__foot">{{ summary?.sleepCount ?? 0 }} 次记录 · 按醒来时间</span>
        </article>
      </div>
    </section>

    <section class="archive-panel">
      <header>
        <div>
          <div>
            <h2>运动记录</h2>
            <p>{{ summary?.latestExercise ? `最近一次 · ${formatDateTime(summary.latestExercise.startedAt)}` : '还没有运动记录' }}</p>
          </div>
        </div>
        <button class="archive-link" type="button" @click="openExercise()">记录运动 <UiIcon name="plus" :size="14" /></button>
      </header>
      <p v-if="!exercises.length" class="activity__empty">记下步行、跑步或其他运动，时长从 1 分钟起。</p>
      <div v-else class="activity-list">
        <article v-for="item in exercises" :key="item.id">
          <div>
            <strong>{{ item.exerciseName }}</strong>
            <span>{{ formatDateTime(item.startedAt) }} · {{ formatDurationMinutes(item.durationMin) }}</span>
            <small v-if="exerciseMeta(item) || item.remark">{{ [exerciseMeta(item), item.remark].filter(Boolean).join(' · ') }}</small>
          </div>
          <div class="activity-list__actions">
            <button type="button" @click="openExercise(item)">修改</button>
            <button type="button" @click="removeExercise(item)">删除</button>
          </div>
        </article>
      </div>
    </section>

    <section class="archive-panel">
      <header>
        <div>
          <div>
            <h2>睡眠记录</h2>
            <p>{{ summary?.latestSleep ? `最近一次 · ${summary.latestSleep.qualityName || '未评分'} · ${formatDurationMinutes(summary.latestSleep.durationMin)}` : '还没有睡眠记录' }}</p>
          </div>
        </div>
        <button class="archive-link" type="button" @click="openSleep()">记录睡眠 <UiIcon name="plus" :size="14" /></button>
      </header>
      <p v-if="!sleeps.length" class="activity__empty">填写入睡和醒来时间，时长会自动计算。</p>
      <div v-else class="activity-list">
        <article v-for="item in sleeps" :key="item.id">
          <div>
            <strong>{{ item.qualityName || '睡眠' }}</strong>
            <span>{{ formatDateTime(item.bedtime) }} – {{ formatDateTime(item.wakeTime) }}</span>
            <small>{{ formatDurationMinutes(item.durationMin) }}<template v-if="item.remark"> · {{ item.remark }}</template></small>
          </div>
          <div class="activity-list__actions">
            <button type="button" @click="openSleep(item)">修改</button>
            <button type="button" @click="removeSleep(item)">删除</button>
          </div>
        </article>
      </div>
    </section>

    <Teleport to="body">
      <div v-if="editor" class="activity-dialog-overlay" role="presentation" @click.self="closeEditor">
        <div class="activity-dialog" role="dialog" aria-modal="true" :aria-label="editor === 'exercise' ? '记录运动' : '记录睡眠'">
          <form v-if="editor === 'exercise'" @submit.prevent="saveExercise">
            <h3>{{ editingId ? '修改运动' : '记录运动' }}</h3>
            <p v-if="message" class="archive-panel__error" role="alert">{{ message }}</p>
            <label>
              运动类型
              <select v-model="exerciseForm.exerciseType" class="input" required>
                <option v-for="item in EXERCISE_TYPES" :key="item.code" :value="item.code">{{ item.name }}</option>
              </select>
            </label>
            <label>开始时间<input v-model="exerciseForm.startedAt" class="input" type="datetime-local" required></label>
            <label>时长（分钟）<input v-model="exerciseForm.durationMin" class="input" type="number" min="1" max="600" step="1" required></label>
            <label>距离（公里，选填）<input v-model="exerciseForm.distanceKm" class="input" type="number" min="0.1" max="300" step="0.1"></label>
            <label>消耗（千卡，选填）<input v-model="exerciseForm.caloriesKcal" class="input" type="number" min="1" max="8000" step="1"></label>
            <label>
              强度（选填）
              <select v-model="exerciseForm.intensity" class="input">
                <option value="">未填写</option>
                <option v-for="item in EXERCISE_INTENSITIES" :key="item.code" :value="item.code">{{ item.name }}</option>
              </select>
            </label>
            <label>备注<input v-model="exerciseForm.remark" class="input" type="text" maxlength="255"></label>
            <div class="activity-dialog__actions">
              <button class="btn btn--ghost" type="button" @click="closeEditor">取消</button>
              <button class="btn btn--primary" type="submit" :disabled="saving">{{ saving ? '保存中…' : '保存' }}</button>
            </div>
          </form>
          <form v-else @submit.prevent="saveSleep">
            <h3>{{ editingId ? '修改睡眠' : '记录睡眠' }}</h3>
            <p v-if="message" class="archive-panel__error" role="alert">{{ message }}</p>
            <label>入睡时间<input v-model="sleepForm.bedtime" class="input" type="datetime-local" required></label>
            <label>醒来时间<input v-model="sleepForm.wakeTime" class="input" type="datetime-local" required></label>
            <p class="activity-dialog__hint">预计时长 {{ previewSleep }}</p>
            <fieldset class="activity-quality">
              <legend>睡眠质量</legend>
              <button
                v-for="item in SLEEP_QUALITIES"
                :key="item.code"
                type="button"
                :class="{ 'is-active': Number(sleepForm.quality) === item.code }"
                @click="sleepForm.quality = item.code"
              >{{ item.name }}</button>
            </fieldset>
            <label>备注<input v-model="sleepForm.remark" class="input" type="text" maxlength="255"></label>
            <div class="activity-dialog__actions">
              <button class="btn btn--ghost" type="button" @click="closeEditor">取消</button>
              <button class="btn btn--primary" type="submit" :disabled="saving">{{ saving ? '保存中…' : '保存' }}</button>
            </div>
          </form>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.activity { display: grid; gap: 16px; }
.activity__ranges { display: flex; gap: 8px; }
.activity__ranges button {
  min-height: 32px;
  padding: 0 12px;
  border: 1px solid #d6e6de;
  border-radius: 999px;
  background: #fff;
  color: #4c6e64;
  font: inherit;
  font-size: 12px;
  font-weight: 750;
  cursor: pointer;
}
.activity__ranges button.is-active { border-color: #0b8878; background: #e7f6f1; color: #0b675a; }
.activity__empty { margin: 0; color: #849d96; font-size: 13px; }
.activity-list { display: grid; }
.activity-list article {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 12px;
  align-items: center;
  padding: 14px 0;
  border-bottom: 1px solid #e6eeea;
}
.activity-list article:last-child { border-bottom: 0; padding-bottom: 0; }
.activity-list strong, .activity-list span, .activity-list small { display: block; }
.activity-list strong { color: #183d36; font-size: 15px; }
.activity-list span { margin-top: 4px; color: #5d786e; font-size: 13px; }
.activity-list small { margin-top: 4px; color: #849d96; font-size: 12px; }
.activity-list__actions { display: flex; gap: 8px; }
.activity-list__actions button {
  border: 0;
  background: transparent;
  color: #0e8175;
  font: inherit;
  font-size: 12px;
  font-weight: 800;
  cursor: pointer;
}
.activity-dialog-overlay {
  position: fixed;
  inset: 0;
  z-index: 40;
  display: grid;
  place-items: center;
  padding: 24px;
  background: rgba(23, 52, 59, .28);
}
.activity-dialog {
  width: min(440px, 100%);
  display: grid;
  padding: 22px;
  border-radius: 18px;
  background: #fff;
  max-height: min(88dvh, 760px);
  overflow: auto;
}
.activity-dialog form { display: grid; gap: 12px; }
.activity-dialog h3 { margin: 0; color: #193f38; }
.activity-dialog label, .activity-quality { display: grid; gap: 6px; margin: 0; border: 0; padding: 0; color: var(--color-text-secondary); font-size: 13px; }
.activity-dialog__hint { margin: 0; color: #0b675a; font-size: 13px; font-weight: 700; }
.activity-quality { display: flex; flex-wrap: wrap; gap: 8px; }
.activity-quality legend { width: 100%; padding: 0; font-size: 13px; }
.activity-quality button {
  min-height: 32px;
  padding: 0 12px;
  border: 1px solid #d6e6de;
  border-radius: 999px;
  background: #fff;
  color: #4c6e64;
  font: inherit;
  font-size: 12px;
  cursor: pointer;
}
.activity-quality button.is-active { border-color: #0b8878; background: #e7f6f1; color: #0b675a; font-weight: 750; }
.activity-dialog__actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 8px; }
@media (max-width: 767px) {
  .activity-list article { grid-template-columns: 1fr; }
}
</style>
