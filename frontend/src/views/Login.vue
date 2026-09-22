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
const showRegisterPassword = ref(false);
const showConfirmPassword = ref(false);
const error = ref("");
const credentialError = ref(false);
const form = reactive({ username: "", password: "" });
const regForm = reactive({
  username: "",
  password: "",
  confirmPassword: "",
  phone: "",
});

async function submitLogin() {
  if (!form.username || !form.password) return showError("请输入用户名和密码", true);
  const result = await login(form.username, form.password);
  if (!result.success) {
    const message = result.error || "登录失败";
    return showError(message, /用户名|密码|账号|凭证|认证失败/.test(message));
  }
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

function showError(message, affectsCredentials = false) {
  error.value = message;
  credentialError.value = affectsCredentials;
  nextTick(() => document.querySelector(".login-error")?.focus());
}

function switchMode(next) {
  showRegister.value = next;
  showPassword.value = false;
  showRegisterPassword.value = false;
  showConfirmPassword.value = false;
  error.value = "";
  credentialError.value = false;
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
      <svg class="login-vital" viewBox="0 0 960 160" aria-hidden="true" preserveAspectRatio="none">
        <defs>
          <linearGradient id="login-vital-gradient" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0" stop-color="#0f8f82" stop-opacity="0" />
            <stop offset=".22" stop-color="#0f8f82" stop-opacity=".8" />
            <stop offset=".78" stop-color="#2aa396" stop-opacity=".8" />
            <stop offset="1" stop-color="#2aa396" stop-opacity="0" />
          </linearGradient>
        </defs>
        <path pathLength="1" d="M0 92H180l20-1 16-16 18 32 23-68 25 53h196l18-1 14-13 18 27 22-53 23 40h391" />
      </svg>
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
                  :aria-invalid="credentialError || undefined"
                  :aria-describedby="credentialError ? 'login-error' : undefined"
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
                    :aria-invalid="credentialError || undefined"
                    :aria-describedby="credentialError ? 'login-error' : undefined"
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
                <div class="login-password-field">
                  <input id="register-password" v-model="regForm.password" class="input" :type="showRegisterPassword ? 'text' : 'password'" placeholder="至少 6 位" autocomplete="new-password" minlength="6" required />
                  <button type="button" :aria-pressed="showRegisterPassword" @click="showRegisterPassword = !showRegisterPassword">{{ showRegisterPassword ? "隐藏" : "显示" }}</button>
                </div>
              </div>
              <div class="form-group">
                <label class="form-label" for="register-confirm-password">确认密码</label>
                <div class="login-password-field">
                  <input id="register-confirm-password" v-model="regForm.confirmPassword" class="input" :type="showConfirmPassword ? 'text' : 'password'" placeholder="再次输入密码" autocomplete="new-password" minlength="6" required />
                  <button type="button" :aria-pressed="showConfirmPassword" @click="showConfirmPassword = !showConfirmPassword">{{ showConfirmPassword ? "隐藏" : "显示" }}</button>
                </div>
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

.login-vital {
  position: absolute;
  top: 50%;
  left: 50%;
  width: min(960px, 92vw);
  height: 160px;
  pointer-events: none;
  opacity: .16;
  filter: drop-shadow(0 6px 14px rgba(15, 143, 130, .08));
  transform: translate(-50%, -53%);
}
.login-vital path {
  fill: none;
  stroke: url(#login-vital-gradient);
  stroke-width: 1.5;
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-dasharray: .18 .82;
  animation: login-vital-trace 7.2s linear infinite;
}

.login-stage { position: relative; z-index: 1; width: min(440px, 100%); display: grid; gap: 22px; }
.login-card {
  width: 100%;
  padding: 38px 40px 30px;
  border: 1px solid var(--color-border);
  border-radius: 18px;
  background: linear-gradient(180deg, rgba(255, 255, 255, .995), rgba(252, 255, 254, .98));
  box-shadow: var(--shadow-clinical);
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
@keyframes login-vital-trace {
  from { stroke-dashoffset: 1; }
  to { stroke-dashoffset: 0; }
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
}

@media (prefers-reduced-motion: reduce) {
  .login-card, .login-vital path { animation: none; }
  .login-form-enter-active, .login-form-leave-active, .login-error-enter-active, .login-error-leave-active { transition-duration: 1ms; }
}
</style>
