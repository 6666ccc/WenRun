<script setup>
import { nextTick, reactive, ref } from "vue";
import { useRouter } from "vue-router";
import { useAuth } from "../stores";
import { homePath } from "../utils/portal";
import { register as registerApi } from "../api/modules/user";
import UiIcon from "../components/UiIcon.vue";

const router = useRouter();
const { login, loading, setSession } = useAuth();
const showRegister = ref(false);
const showPassword = ref(false);
const error = ref("");
const form = reactive({ username: "", password: "" });
const regForm = reactive({
  username: "",
  password: "",
  confirmPassword: "",
  phone: "",
});

async function submitLogin() {
  if (!form.username || !form.password) return showError("请输入用户名和密码");
  const result = await login(form.username, form.password);
  if (!result.success) return showError(result.error || "登录失败");
  router.replace(homePath());
}

async function submitRegister() {
  if (regForm.password !== regForm.confirmPassword)
    return showError("两次密码输入不一致");
  if (regForm.password.length < 6) return showError("密码至少 6 位");
  try {
    const data = await registerApi(regForm);
    setSession(data);
    router.replace(homePath());
  } catch (nextError) {
    showError(nextError.message || "注册失败");
  }
}

function showError(message) {
  error.value = message;
  nextTick(() => document.querySelector(".login-error")?.focus());
}

function switchMode(next) {
  showRegister.value = next;
  showPassword.value = false;
  error.value = "";
}

</script>

<template>
  <div class="login-scene">
    <header class="login-topbar">
      <div class="login-brand" aria-label="温润医院患者服务">
        <span class="login-brand__mark" aria-hidden="true"><UiIcon name="logo" :size="22" /></span>
        <span><strong>温润医院</strong><small>患者服务</small></span>
      </div>
      <p class="login-emergency"><UiIcon name="alert" :size="15" />急症请拨打 120</p>
    </header>

    <main class="login-form-panel">
      <div class="login-stage">
        <section class="login-card" :aria-labelledby="showRegister ? 'register-title' : 'login-title'">
          <header class="login-heading">
            <p>{{ showRegister ? "新患者账户" : "患者账户" }}</p>
            <h1 :id="showRegister ? 'register-title' : 'login-title'">
              {{ showRegister ? "创建账户" : "欢迎回来" }}
            </h1>
          </header>

          <Transition name="login-error">
            <div v-if="error" id="login-error" class="login-error" role="alert" tabindex="-1">
              <UiIcon name="alert" :size="17" />
              <span><strong>无法继续</strong>{{ error }}</span>
            </div>
          </Transition>

          <Transition name="login-form" mode="out-in" appear>
            <form v-if="!showRegister" key="login" class="login-form" @submit.prevent="submitLogin">
              <div class="form-group">
                <label class="form-label" for="login-username">用户名</label>
                <input
                  id="login-username"
                  v-model="form.username"
                  class="input"
                  placeholder="输入用户名"
                  autocomplete="username"
                  required
                  :aria-invalid="!!error"
                  :aria-describedby="error ? 'login-error' : undefined"
                />
              </div>
              <div class="form-group">
                <label class="form-label" for="login-password">密码</label>
                <div class="login-password-field">
                  <input
                    id="login-password"
                    v-model="form.password"
                    class="input"
                    :type="showPassword ? 'text' : 'password'"
                    placeholder="输入密码"
                    autocomplete="current-password"
                    required
                    :aria-invalid="!!error"
                    :aria-describedby="error ? 'login-error' : undefined"
                  />
                  <button type="button" :aria-pressed="showPassword" @click="showPassword = !showPassword">
                    {{ showPassword ? "隐藏" : "显示" }}
                  </button>
                </div>
              </div>
              <button class="btn btn--primary btn--lg login-submit" :disabled="loading">
                <span>{{ loading ? "登录中…" : "登录" }}</span>
                <UiIcon v-if="!loading" name="arrowRight" :size="18" />
              </button>
              <p class="login-switch">
                还没有账户？
                <button type="button" @click="switchMode(true)">立即注册</button>
              </p>
            </form>

            <form v-else key="register" class="login-form" @submit.prevent="submitRegister">
              <div class="form-group">
                <label class="form-label" for="register-username">用户名</label>
                <input id="register-username" v-model="regForm.username" class="input" placeholder="设置用户名" autocomplete="username" required />
              </div>
              <div class="form-group">
                <label class="form-label" for="register-password">密码</label>
                <input id="register-password" v-model="regForm.password" class="input" type="password" placeholder="至少 6 位" autocomplete="new-password" minlength="6" required />
              </div>
              <div class="form-group">
                <label class="form-label" for="register-confirm-password">确认密码</label>
                <input id="register-confirm-password" v-model="regForm.confirmPassword" class="input" type="password" placeholder="再次输入密码" autocomplete="new-password" minlength="6" required />
              </div>
              <div class="form-group">
                <label class="form-label" for="register-phone">手机号</label>
                <input id="register-phone" v-model="regForm.phone" class="input" placeholder="输入手机号" autocomplete="tel" inputmode="tel" required />
              </div>
              <button class="btn btn--primary btn--lg login-submit" :disabled="loading">
                <span>{{ loading ? "注册中…" : "注册并登录" }}</span>
                <UiIcon v-if="!loading" name="arrowRight" :size="18" />
              </button>
              <p class="login-switch">
                已有账户？
                <button type="button" @click="switchMode(false)">返回登录</button>
              </p>
            </form>
          </Transition>
        </section>

        <div class="login-route" aria-hidden="true">
          <span class="login-route__track" />
          <span class="login-route__node login-route__node--start" />
          <span class="login-route__node login-route__node--middle" />
          <span class="login-route__node login-route__node--end" />
          <span class="login-route__pulse" />
        </div>
      </div>
    </main>
  </div>
</template>

<style scoped>
.login-scene {
  position: relative;
  min-height: 100dvh;
  display: grid;
  grid-template-rows: auto 1fr;
  overflow: hidden;
  background: #f5f8f7;
}

.login-scene::before {
  content: "";
  position: absolute;
  inset: 0;
  pointer-events: none;
  background: radial-gradient(circle at 50% 54%, rgba(15, 118, 110, .055), transparent 28rem);
}

.login-topbar {
  position: relative;
  z-index: 1;
  width: min(1240px, 100%);
  min-height: 86px;
  margin: 0 auto;
  padding: 22px 38px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
}

.login-brand { display: flex; align-items: center; gap: 11px; }
.login-brand__mark {
  width: 42px;
  height: 42px;
  display: grid;
  place-items: center;
  flex: 0 0 42px;
  border-radius: 12px;
  background: var(--color-brand-800);
  color: #fff;
  box-shadow: 0 7px 16px rgba(7, 95, 88, .16);
}
.login-brand strong, .login-brand small { display: block; }
.login-brand strong { color: var(--color-text); font-size: 17px; letter-spacing: .02em; }
.login-brand small { margin-top: 2px; color: var(--color-text-secondary); font-size: 12px; }

.login-emergency {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  margin: 0;
  color: #7c4a12;
  font-size: 13px;
  font-weight: 650;
}

.login-form-panel {
  position: relative;
  z-index: 1;
  display: grid;
  place-items: center;
  min-width: 0;
  padding: 10px 24px 30px;
}

.login-stage { width: min(440px, 100%); display: grid; gap: 22px; }
.login-card {
  width: 100%;
  padding: 38px 40px 30px;
  border: 1px solid var(--color-border);
  border-radius: 18px;
  background: rgba(255, 255, 255, .98);
  box-shadow: 0 18px 48px rgba(7, 63, 59, .09);
  animation: login-card-in 420ms var(--ease-enter) both;
}

.login-heading { margin-bottom: 28px; }
.login-heading p {
  margin: 0 0 7px;
  color: var(--color-brand-700);
  font-size: 12px;
  font-weight: 750;
  letter-spacing: .08em;
}
.login-heading h1 { margin: 0; font-size: 30px; line-height: 1.24; letter-spacing: -.035em; }

.login-error {
  display: flex;
  align-items: flex-start;
  gap: 9px;
  margin: -5px 0 20px;
  padding: 12px 13px;
  border: 1px solid #e8aaa4;
  border-radius: 10px;
  background: var(--color-danger-bg);
  color: var(--color-danger);
  font-size: 13px;
}
.login-error svg { flex: 0 0 auto; margin-top: 2px; }
.login-error span, .login-error strong { display: block; }
.login-error strong { margin-bottom: 2px; }

.login-form { display: grid; gap: 20px; }
.login-form .form-group { display: grid; gap: 8px; margin: 0; }
.login-form .form-label { font-size: 14px; }
.login-form .input { width: 100%; min-height: 50px; padding-inline: 15px; font-size: 16px; }
.login-password-field { position: relative; }
.login-password-field .input { padding-right: 72px; }
.login-password-field button {
  position: absolute;
  top: 50%;
  right: 8px;
  min-width: 54px;
  min-height: 36px;
  padding: 0 8px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: var(--color-brand-700);
  cursor: pointer;
  font: inherit;
  font-size: 13px;
  font-weight: 700;
  transform: translateY(-50%);
}
.login-password-field button:hover { background: var(--color-mint-050); }

.login-submit {
  width: 100%;
  min-height: 50px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 9px;
  margin-top: 2px;
}
.login-submit svg { transition: transform var(--motion-fast) var(--ease-standard); }
.login-submit:hover:not(:disabled) svg, .login-submit:focus-visible svg { transform: translateX(4px); }

.login-switch { margin: -2px 0 0; color: var(--color-text-secondary); font-size: 14px; text-align: center; }
.login-switch button {
  min-height: 36px;
  padding: 2px 4px;
  border: 0;
  background: none;
  color: var(--color-brand-700);
  cursor: pointer;
  font: inherit;
  font-weight: 750;
}

.login-route { position: relative; width: 286px; height: 18px; margin: 0 auto; }
.login-route__track {
  position: absolute;
  top: 8px;
  left: 0;
  right: 0;
  height: 1px;
  overflow: hidden;
  background: var(--color-border);
}
.login-route__track::after {
  content: "";
  position: absolute;
  inset: 0;
  background: var(--color-brand-700);
  transform: scaleX(0);
  transform-origin: left;
  animation: login-route-draw 720ms 180ms var(--ease-enter) both;
}
.login-route__node, .login-route__pulse {
  position: absolute;
  top: 4px;
  width: 9px;
  height: 9px;
  border: 2px solid #f5f8f7;
  border-radius: 50%;
  background: var(--color-brand-700);
  box-shadow: 0 0 0 1px var(--color-border-strong);
}
.login-route__node--start { left: 0; }
.login-route__node--middle { left: calc(50% - 4px); }
.login-route__node--end { right: 0; }
.login-route__pulse {
  left: 0;
  z-index: 2;
  background: var(--color-mint-300);
  box-shadow: 0 0 0 5px rgba(15, 118, 110, .11);
  animation: login-route-travel 5.6s 1.1s var(--ease-standard) infinite;
}

.login-form-enter-active { transition: opacity 240ms var(--ease-enter), transform 240ms var(--ease-enter); }
.login-form-leave-active { transition: opacity 130ms var(--ease-exit), transform 130ms var(--ease-exit); }
.login-form-enter-from { opacity: 0; transform: translateY(7px); }
.login-form-leave-to { opacity: 0; transform: translateY(-4px); }
.login-error-enter-active, .login-error-leave-active { transition: opacity 180ms var(--ease-enter), transform 180ms var(--ease-enter); }
.login-error-enter-from, .login-error-leave-to { opacity: 0; transform: translateY(-6px); }

@keyframes login-card-in {
  from { opacity: 0; transform: translateY(14px) scale(.992); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}
@keyframes login-route-draw { to { transform: scaleX(1); } }
@keyframes login-route-travel {
  0%, 12% { left: 0; opacity: 0; }
  18% { opacity: 1; }
  82% { opacity: 1; }
  88%, 100% { left: calc(100% - 9px); opacity: 0; }
}

@media (max-width: 540px) {
  .login-topbar { min-height: 72px; padding: 15px 18px; }
  .login-brand__mark { width: 38px; height: 38px; flex-basis: 38px; border-radius: 10px; }
  .login-brand strong { font-size: 15px; }
  .login-brand small { font-size: 11px; }
  .login-emergency { gap: 5px; font-size: 12px; }
  .login-form-panel { place-items: start center; padding: 18px 14px 40px; }
  .login-card { padding: 30px 22px 24px; border-radius: 15px; }
  .login-heading { margin-bottom: 24px; }
  .login-heading h1 { font-size: 27px; }
  .login-form { gap: 18px; }
  .login-route { width: 220px; }
}

@media (prefers-reduced-motion: reduce) {
  .login-card, .login-route__track::after, .login-route__pulse { animation: none; }
  .login-route__track::after { transform: scaleX(1); }
  .login-route__pulse { display: none; }
  .login-form-enter-active, .login-form-leave-active, .login-error-enter-active, .login-error-leave-active { transition-duration: 1ms; }
}
</style>
