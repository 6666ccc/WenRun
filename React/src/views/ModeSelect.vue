<script setup>
import { useRouter } from 'vue-router'
import { useAuth } from '../store'
import { MODE_AGENT, MODE_CLASSIC, readMode, writeMode } from '../features/experience/mode'

const router = useRouter()
const { user } = useAuth()
const recentMode = readMode()
const modes = [
  { id: MODE_AGENT, eyebrow: '推荐体验', title: '新版 · AI 随身诊室', description: '说出身体困扰或就医需求，由智能体协助分诊、查询和办理。', path: '/assistant' },
  { id: MODE_CLASSIC, eyebrow: '熟悉的操作方式', title: '传统版 · 自助服务', description: '通过清晰的菜单办理挂号、缴费、科室查询和个人服务。', path: '/home' },
]
function choose(mode) { writeMode(mode.id); router.replace(mode.path) }
</script>

<template>
  <main class="mode-select">
    <section class="mode-select__intro"><p>WENRUN CARE · 患者端</p><h1>你好，{{ user?.realName || user?.username || '患者' }}。<br>今天想怎样使用医院？</h1><span>两种方式共享同一个账户、预约与就诊记录。</span></section>
    <section class="mode-select__cards" aria-label="选择使用方式">
      <button v-for="mode in modes" :key="mode.id" class="mode-card" :class="[`mode-card--${mode.id}`, { 'is-recent': recentMode === mode.id }]" @click="choose(mode)">
        <small>{{ recentMode === mode.id ? '上次使用' : mode.eyebrow }}</small><strong>{{ mode.title }}</strong><span>{{ mode.description }}</span><b>进入体验 →</b>
      </button>
    </section>
  </main>
</template>
