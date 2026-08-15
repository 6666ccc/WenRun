<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth } from '../stores'
import { homePath } from '../utils/portal'
import { register as registerApi } from '../api/modules/user'
import UiIcon from '../components/UiIcon.vue'

const router = useRouter()
const { login, loading, setSession } = useAuth()
const showRegister = ref(false)
const error = ref('')
const form = reactive({ username: '', password: '' })
const regForm = reactive({ username: '', password: '', confirmPassword: '', phone: '' })

async function submitLogin() {
  if (!form.username || !form.password) return void (error.value = '请输入用户名和密码')
  const result = await login(form.username, form.password)
  if (!result.success) return void (error.value = result.error || '登录失败')
  const saved = JSON.parse(localStorage.getItem('wenrun_user') || '{}')
  router.replace(homePath(saved.portalType))
}

async function submitRegister() {
  if (regForm.password !== regForm.confirmPassword) return void (error.value = '两次密码输入不一致')
  if (regForm.password.length < 6) return void (error.value = '密码至少 6 位')
  try {
    const data = await registerApi(regForm)
    setSession(data)
    router.replace(homePath(data.portalType))
  } catch (nextError) {
    error.value = nextError.message || '注册失败'
  }
}

function switchMode(next) {
  showRegister.value = next
  error.value = ''
}
</script>

<template>
  <div class="login-scene view-grain">
    <aside class="login-scene__brand">
      <div class="login-scene__brand-glow" /><div class="login-scene__brand-deco">温</div>
      <div><p class="login-scene__brand-tagline">Warm Clinic</p><h1>温润诊所</h1></div>
      <blockquote class="login-scene__brand-quote">以温润之心，行精准之医。<br>智慧诊疗，从此触手可及。</blockquote>
    </aside>
    <div class="login-scene__form-panel">
      <div class="login-card">
        <div class="login-heading">
          <div class="login-card__logo"><UiIcon name="logo" /></div>
          <h1>{{ showRegister ? '创建账户' : '欢迎回来' }}</h1>
          <p>{{ showRegister ? '注册患者账户，即可在线挂号与缴费' : '登录您的患者账户' }}</p>
        </div>
        <div v-if="error" class="login-error">{{ error }}</div>
        <form v-if="!showRegister" @submit.prevent="submitLogin">
          <div class="form-group mb-md"><label class="form-label">用户名</label><input v-model="form.username" class="input" placeholder="输入用户名" autocomplete="username"></div>
          <div class="form-group mb-md"><label class="form-label">密码</label><input v-model="form.password" class="input" type="password" placeholder="输入密码" autocomplete="current-password"></div>
          <button class="btn btn--primary btn--lg login-submit" :disabled="loading">{{ loading ? '登录中…' : '登录' }}</button>
          <p class="login-switch">还没有账户？ <button type="button" @click="switchMode(true)">立即注册</button></p>
        </form>
        <form v-else @submit.prevent="submitRegister">
          <div class="form-group mb-md"><label class="form-label">用户名</label><input v-model="regForm.username" class="input" placeholder="设置登录用户名"></div>
          <div class="form-group mb-md"><label class="form-label">密码（至少 6 位）</label><input v-model="regForm.password" class="input" type="password" placeholder="设置密码"></div>
          <div class="form-group mb-md"><label class="form-label">确认密码</label><input v-model="regForm.confirmPassword" class="input" type="password" placeholder="再次输入密码"></div>
          <div class="form-group mb-md"><label class="form-label">手机号</label><input v-model="regForm.phone" class="input" placeholder="输入手机号"></div>
          <button class="btn btn--primary btn--lg login-submit" :disabled="loading">{{ loading ? '注册中…' : '注册并登录' }}</button>
          <p class="login-switch">已有账户？ <button type="button" @click="switchMode(false)">返回登录</button></p>
        </form>
        <div class="login-demo"><p class="login-demo__title">演示账号（密码为 password）</p><p>患者：patient01</p></div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.login-heading{text-align:center;margin-bottom:28px}.login-heading h1{font-family:var(--font-serif);font-size:1.5rem;color:var(--c-brand);margin:0}.login-heading p{color:var(--c-sub);font-size:.88rem;margin-top:8px}
.login-error{background:var(--c-danger-bg);color:var(--c-danger);padding:10px 16px;border-radius:var(--radius);font-size:.85rem;margin-bottom:20px}.login-submit{width:100%;margin-top:8px}
.login-switch{text-align:center;margin-top:20px;font-size:.85rem;color:var(--c-sub)}.login-switch button{background:none;border:0;color:var(--c-accent);cursor:pointer;font-weight:500}
</style>
