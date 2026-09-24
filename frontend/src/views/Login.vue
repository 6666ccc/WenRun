<script setup>
import { nextTick, onBeforeUnmount, reactive, ref } from "vue";
import { useRouter } from "vue-router";
import {
  Activity,
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  Cross,
  Eye,
  EyeOff,
  HeartPulse,
  Lock,
  Phone,
  Pill,
  Stethoscope,
  UserRound,
} from "@lucide/vue";
import { useAuth } from "../stores";
import { homePath } from "../utils/portal";
import { register as registerApi } from "../api/modules/user";

const router = useRouter();
const { login, loading, setSession } = useAuth();
const mode = ref("login");
const target = ref("login");
const phase = ref("visible");
const showLoginPassword = ref(false);
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
let switchTimer = 0;

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
  nextTick(() => document.querySelector(".auth-error")?.focus());
}

function resetSecrets() {
  showLoginPassword.value = false;
  showRegisterPassword.value = false;
  showConfirmPassword.value = false;
  error.value = "";
  credentialError.value = false;
}

function switchMode(next) {
  if (next === mode.value || phase.value !== "visible") return;
  resetSecrets();
  if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) {
    target.value = next;
    mode.value = next;
    phase.value = "visible";
    return;
  }
  phase.value = "leaving";
  window.clearTimeout(switchTimer);
  switchTimer = window.setTimeout(() => {
    target.value = next;
    mode.value = next;
    phase.value = "moving";
    switchTimer = window.setTimeout(() => {
      phase.value = "entering";
      requestAnimationFrame(() => requestAnimationFrame(() => {
        phase.value = "visible";
      }));
    }, 820);
  }, 1020);
}

onBeforeUnmount(() => window.clearTimeout(switchTimer));
</script>

<template>
  <main class="auth-shell">
    <div class="auth-scene">
      <div class="auth-card" :class="{ reversed: target === 'register' }">
        <svg class="auth-pattern" viewBox="0 0 1080 640" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
          <defs>
            <pattern id="auth-dots" width="26" height="26" patternUnits="userSpaceOnUse">
              <circle cx="2" cy="2" r="1.15" fill="rgba(255,255,255,.18)" />
            </pattern>
          </defs>
          <rect width="1080" height="640" fill="url(#auth-dots)" />
          <circle cx="160" cy="120" r="90" fill="rgba(255,255,255,.05)" />
          <circle cx="430" cy="520" r="130" fill="rgba(255,255,255,.04)" />
        </svg>

        <section class="tone-panel" aria-label="温润医院">
          <div class="auth-brand" :class="phase">
            <HeartPulse :size="22" aria-hidden="true" />
            <span><strong>温润</strong>医院</span>
          </div>

          <div class="medical-illustration" :class="phase" role="img" aria-label="听诊器、药片与急救标志组成的医疗插画">
            <div class="medical-glow medical-piece medical-backdrop" aria-hidden="true" />
            <div class="medical-orbit orbit-outer medical-piece medical-backdrop" aria-hidden="true" />
            <div class="medical-orbit orbit-inner medical-piece medical-backdrop" aria-hidden="true" />
            <div class="medical-center medical-piece" aria-hidden="true">
              <Stethoscope :size="148" />
              <span class="pulse-mark"><Activity :size="22" /></span>
            </div>
            <span class="medical-badge badge-pill medical-piece" aria-hidden="true"><Pill :size="42" /></span>
            <span class="medical-badge badge-capsule medical-piece" aria-hidden="true"><Pill :size="34" /></span>
            <span class="medical-badge badge-kit medical-piece" aria-hidden="true"><Cross :size="36" /></span>
            <span class="medical-tablet tablet-one medical-piece" aria-hidden="true" />
            <span class="medical-tablet tablet-two medical-piece" aria-hidden="true" />
          </div>

          <p class="tone-caption" :class="phase">
            <span class="caption-line" />
            {{ target === "register" ? "健康旅程从这里开始" : "照护，由此相连" }}
          </p>
        </section>

        <section class="white-panel" :aria-label="mode === 'login' ? '登录表单' : '注册表单'">
          <div class="form-content" :class="phase">
            <header class="title-group">
              <h1 :id="mode === 'login' ? 'login-title' : 'register-title'">
                {{ mode === "login" ? "欢迎回来" : "创建账户" }}
              </h1>
              <p>{{ mode === "login" ? "登录你的患者账户" : "加入温润医院患者服务" }}</p>
            </header>

            <form v-if="mode === 'login'" key="login" @submit.prevent="submitLogin">
              <div v-if="error" id="login-error" class="auth-error" role="alert" tabindex="-1">
                <AlertCircle :size="16" aria-hidden="true" />
                <span>{{ error }}</span>
              </div>
              <div class="fields">
                <label class="auth-field">
                  <UserRound :size="17" aria-hidden="true" />
                  <span class="sr-only">用户名</span>
                  <input
                    id="login-username"
                    v-model="form.username"
                    placeholder="用户名"
                    autocomplete="username"
                    required
                    :aria-invalid="credentialError || undefined"
                    :aria-describedby="credentialError ? 'login-error' : undefined"
                  />
                </label>
                <label class="auth-field">
                  <Lock :size="17" aria-hidden="true" />
                  <span class="sr-only">密码</span>
                  <input
                    id="login-password"
                    v-model="form.password"
                    :type="showLoginPassword ? 'text' : 'password'"
                    placeholder="密码"
                    autocomplete="current-password"
                    required
                    :aria-invalid="credentialError || undefined"
                    :aria-describedby="credentialError ? 'login-error' : undefined"
                  />
                  <button type="button" class="eye-button" :aria-pressed="showLoginPassword" :aria-label="showLoginPassword ? '隐藏密码' : '显示密码'" @click="showLoginPassword = !showLoginPassword">
                    <EyeOff v-if="showLoginPassword" :size="16" />
                    <Eye v-else :size="16" />
                  </button>
                </label>
              </div>
              <button class="primary-button" type="submit" :disabled="loading">
                {{ loading ? "登录中…" : "登录" }}
                <ArrowRight v-if="!loading" :size="15" aria-hidden="true" />
              </button>
              <p class="bottom-prompt">
                还没有账户？
                <button type="button" @click="switchMode('register')">立即注册 <ArrowRight :size="13" aria-hidden="true" /></button>
              </p>
            </form>

            <form v-else key="register" @submit.prevent="submitRegister">
              <div v-if="error" id="login-error" class="auth-error" role="alert" tabindex="-1">
                <AlertCircle :size="16" aria-hidden="true" />
                <span>{{ error }}</span>
              </div>
              <div class="fields register-fields">
                <label class="auth-field">
                  <UserRound :size="17" aria-hidden="true" />
                  <span class="sr-only">用户名</span>
                  <input id="register-username" v-model="regForm.username" placeholder="用户名" autocomplete="username" required />
                </label>
                <label class="auth-field">
                  <Lock :size="17" aria-hidden="true" />
                  <span class="sr-only">密码</span>
                  <input id="register-password" v-model="regForm.password" :type="showRegisterPassword ? 'text' : 'password'" placeholder="密码，至少 6 位" autocomplete="new-password" minlength="6" required />
                  <button type="button" class="eye-button" :aria-pressed="showRegisterPassword" :aria-label="showRegisterPassword ? '隐藏密码' : '显示密码'" @click="showRegisterPassword = !showRegisterPassword">
                    <EyeOff v-if="showRegisterPassword" :size="16" />
                    <Eye v-else :size="16" />
                  </button>
                </label>
                <label class="auth-field">
                  <Lock :size="17" aria-hidden="true" />
                  <span class="sr-only">确认密码</span>
                  <input id="register-confirm-password" v-model="regForm.confirmPassword" :type="showConfirmPassword ? 'text' : 'password'" placeholder="确认密码" autocomplete="new-password" minlength="6" required />
                  <button type="button" class="eye-button" :aria-pressed="showConfirmPassword" :aria-label="showConfirmPassword ? '隐藏确认密码' : '显示确认密码'" @click="showConfirmPassword = !showConfirmPassword">
                    <EyeOff v-if="showConfirmPassword" :size="16" />
                    <Eye v-else :size="16" />
                  </button>
                </label>
                <label class="auth-field">
                  <Phone :size="17" aria-hidden="true" />
                  <span class="sr-only">手机号</span>
                  <input id="register-phone" v-model="regForm.phone" placeholder="手机号" autocomplete="tel" inputmode="tel" required />
                </label>
              </div>
              <button class="primary-button" type="submit" :disabled="loading">
                {{ loading ? "注册中…" : "注册并登录" }}
                <ArrowRight v-if="!loading" :size="15" aria-hidden="true" />
              </button>
              <p class="bottom-prompt">
                已有账户？
                <button type="button" @click="switchMode('login')"><ArrowLeft :size="13" aria-hidden="true" /> 返回登录</button>
              </p>
            </form>
          </div>
        </section>
      </div>
    </div>
  </main>
</template>

<style scoped>
.auth-shell {
  min-height: 100dvh;
  display: grid;
  place-items: center;
  padding: 34px 18px 28px;
  background:
    radial-gradient(ellipse at 50% 0%, rgba(15, 143, 130, .1), transparent 34rem),
    #f4f8f7;
  color: #143833;
}

.auth-scene { width: min(1080px, 100%); }

.auth-card {
  height: 640px;
  position: relative;
  overflow: hidden;
  border: 4px solid #0a564f;
  border-radius: 22px;
  background: #0c746c;
  box-shadow: 0 28px 46px rgba(7, 91, 85, .22), 0 64px 85px rgba(7, 91, 85, .09);
}

.auth-pattern {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}

.tone-panel,
.white-panel {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 50%;
}

.tone-panel { left: 0; transition: left .8s cubic-bezier(.76, 0, .24, 1); }
.auth-card.reversed .tone-panel { left: 50%; }

.white-panel {
  left: 50%;
  z-index: 2;
  background: #fff;
  border-radius: 14px 0 0 14px;
  transition: left .8s cubic-bezier(.76, 0, .24, 1), border-radius .8s;
}
.auth-card.reversed .white-panel { left: 0; border-radius: 0 14px 14px 0; }

.auth-brand {
  position: absolute;
  top: 22px;
  left: 28px;
  z-index: 1;
  display: flex;
  align-items: center;
  gap: 8px;
  color: #fff;
  font-size: 17px;
  letter-spacing: .02em;
  opacity: 1;
  transition: opacity .22s ease, transform .32s ease;
}
.auth-brand.leaving,
.auth-brand.moving,
.auth-brand.entering { opacity: 0; transform: translateY(-16px); }
.auth-brand strong { font-weight: 800; }
.auth-card.reversed .auth-brand { left: auto; right: 28px; }

.medical-illustration {
  --medical-travel: -360px;
  position: absolute;
  left: 50%;
  top: 51%;
  width: min(390px, 76%);
  aspect-ratio: 1;
  transform: translate(-50%, -50%);
  filter: drop-shadow(0 22px 24px rgba(4, 48, 44, .22));
}
.medical-piece {
  opacity: 1;
  translate: 0 0;
  transition: opacity .3s ease, translate .7s cubic-bezier(.22, 1, .36, 1);
  transition-delay: calc(var(--enter-delay, 0s) + .08s), var(--enter-delay, 0s);
}
.medical-illustration.leaving .medical-piece {
  opacity: 0;
  translate: 0 var(--medical-travel);
  transition-duration: .16s, .7s;
  transition-timing-function: ease, cubic-bezier(.55, .06, .68, .19);
  transition-delay: calc(var(--leave-delay, 0s) + .5s), var(--leave-delay, 0s);
}
.medical-illustration.moving .medical-piece,
.medical-illustration.entering .medical-piece {
  opacity: 0;
  translate: 0 var(--medical-travel);
  transition: none;
}
.medical-backdrop { --leave-delay: .14s; --enter-delay: .19s; }
.medical-glow {
  position: absolute;
  inset: 12%;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(186, 244, 236, .5) 0, rgba(90, 196, 184, .18) 42%, rgba(90, 196, 184, 0) 72%);
  animation: medical-breathe 4.8s ease-in-out infinite;
}
.medical-orbit {
  position: absolute;
  left: 50%;
  top: 50%;
  border: 1px solid rgba(214, 247, 242, .38);
  border-radius: 50%;
}
.orbit-outer { width: 92%; height: 68%; transform: translate(-50%, -50%) rotate(-14deg); }
.orbit-inner { width: 67%; height: 88%; transform: translate(-50%, -50%) rotate(22deg); border-style: dashed; }
.medical-center {
  --leave-delay: .165s;
  --enter-delay: .225s;
  position: absolute;
  left: 50%;
  top: 50%;
  width: 52%;
  aspect-ratio: 1;
  display: grid;
  place-items: center;
  border-radius: 42% 58% 56% 44% / 47% 42% 58% 53%;
  color: #0c5c56;
  background: linear-gradient(145deg, #fff 0%, #dff8f4 100%);
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, .9), 0 18px 44px rgba(6, 48, 44, .28);
  transform: translate(-50%, -50%);
}
.medical-center :deep(svg) { width: 58%; height: 58%; animation: medical-glyph-float 4.6s ease-in-out infinite; }
.pulse-mark {
  position: absolute;
  right: 9%;
  bottom: 12%;
  width: 43px;
  height: 43px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  color: #fff;
  background: #0aa3b5;
  box-shadow: 0 8px 20px rgba(6, 140, 158, .38);
}
.medical-badge {
  position: absolute;
  display: grid;
  place-items: center;
  border: 1px solid rgba(255, 255, 255, .76);
  background: rgba(241, 252, 250, .94);
  box-shadow: 0 12px 27px rgba(8, 48, 44, .2);
  color: #128f86;
}
.medical-badge :deep(svg) { animation: medical-glyph-float 4.2s ease-in-out infinite; }
.badge-pill {
  --leave-delay: .11s;
  --enter-delay: .15s;
  left: 2%;
  top: 24%;
  width: 82px;
  height: 82px;
  border-radius: 28px;
  transform: rotate(-19deg);
}
.badge-pill :deep(svg) { animation-delay: -1.1s; }
.badge-capsule {
  --leave-delay: .055s;
  --enter-delay: .075s;
  right: 5%;
  top: 15%;
  width: 68px;
  height: 68px;
  border-radius: 50%;
  color: #ff7890;
  transform: rotate(32deg);
}
.badge-capsule :deep(svg) { animation-delay: -2.4s; }
.badge-kit {
  --leave-delay: .275s;
  --enter-delay: .375s;
  right: 2%;
  bottom: 16%;
  width: 78px;
  height: 78px;
  border-radius: 26px;
  color: #d7a23a;
}
.badge-kit :deep(svg) { animation-delay: -.4s; }
.medical-tablet {
  position: absolute;
  width: 29px;
  height: 29px;
  border: 7px solid #8edfd4;
  border-radius: 50%;
  background: #fff;
  box-shadow: 0 8px 14px rgba(8, 48, 44, .2);
}
.tablet-one { --leave-delay: .22s; --enter-delay: .3s; left: 16%; bottom: 14%; }
.tablet-two { --leave-delay: 0s; --enter-delay: 0s; right: 24%; top: 4%; width: 19px; height: 19px; border-width: 5px; }

.tone-caption {
  position: absolute;
  bottom: 26px;
  left: 30px;
  display: flex;
  align-items: center;
  gap: 9px;
  margin: 0;
  color: #e7f7f4;
  font-size: 13px;
  font-weight: 700;
  letter-spacing: .12em;
  transition: opacity .3s, transform .4s;
}
.tone-caption.leaving,
.tone-caption.moving,
.tone-caption.entering { opacity: 0; transform: translateY(-12px); }
.caption-line { width: 17px; height: 1px; background: #9ee4da; }
.auth-card.reversed .tone-caption { left: auto; right: 30px; }

.form-content {
  position: absolute;
  top: 50%;
  left: 50%;
  width: min(360px, 82%);
  text-align: center;
  transition: opacity .25s, transform .4s;
}
.form-content.leaving { opacity: 0; transform: translate(-50%, -43%); }
.form-content.moving,
.form-content.entering { opacity: 0; transform: translate(-50%, -55%); }
.form-content.visible { opacity: 1; transform: translate(-50%, -50%); }

.title-group { margin-bottom: 26px; }
.title-group h1 {
  margin: 0 0 6px;
  color: #0d4f4a;
  font-size: 32px;
  font-weight: 800;
  line-height: 1.2;
  letter-spacing: -.03em;
}
.title-group p { margin: 0; color: #8aa09b; font-size: 14px; }

.fields { display: grid; gap: 12px; }
.register-fields { gap: 10px; }
.auth-field {
  display: flex;
  align-items: center;
  width: 100%;
  height: 48px;
  gap: 10px;
  padding: 0 8px 0 16px;
  border: 1px solid transparent;
  border-radius: 999px;
  background: #f2f6f5;
  color: #6d8883;
  transition: background .2s, border-color .2s, box-shadow .2s;
}
.auth-field:focus-within {
  background: #fff;
  border-color: #3aafa3;
  box-shadow: 0 0 0 3px rgba(15, 143, 130, .14);
}
.auth-field:has(input[aria-invalid="true"]) {
  background: #fff7f6;
  border-color: #e7aaa4;
}
.auth-field input {
  width: 100%;
  min-width: 0;
  border: 0;
  outline: none;
  background: transparent;
  color: #143833;
  font-size: 16px;
  font-weight: 650;
}
.auth-field input::placeholder { color: #8aa09b; font-weight: 600; opacity: 1; }
.auth-field input:focus-visible { outline: none; box-shadow: none; }
.eye-button {
  display: grid;
  place-items: center;
  width: 36px;
  height: 36px;
  flex: 0 0 36px;
  padding: 0;
  border: 0;
  border-radius: 50%;
  background: transparent;
  color: #7d968f;
  cursor: pointer;
}
.eye-button:hover { background: rgba(15, 143, 130, .08); color: #0c746c; }

.primary-button {
  min-width: 148px;
  height: 46px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  margin-top: 22px;
  padding: 0 22px;
  border: 0;
  border-radius: 999px;
  background: #0aa3b5;
  color: #fff;
  box-shadow: 0 8px 16px rgba(8, 150, 168, .2);
  font-size: 15px;
  font-weight: 800;
  letter-spacing: .04em;
  cursor: pointer;
  transition: background .2s, transform .2s, box-shadow .2s;
}
.primary-button:hover:not(:disabled) {
  background: #078fa0;
  transform: translateY(-2px);
  box-shadow: 0 12px 20px rgba(8, 150, 168, .26);
}
.primary-button:disabled { opacity: .72; cursor: wait; }
.register-fields + .primary-button { margin-top: 16px; }

.bottom-prompt { margin: 18px 0 0; color: #8aa09b; font-size: 14px; }
.bottom-prompt button {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px;
  border: 0;
  background: none;
  color: #0c746c;
  font: inherit;
  font-weight: 800;
  cursor: pointer;
}
.bottom-prompt button:hover { text-decoration: underline; }

.auth-error {
  display: flex;
  align-items: flex-start;
  justify-content: center;
  gap: 7px;
  margin: -8px 0 16px;
  color: #a61b16;
  font-size: 13px;
  font-weight: 700;
  line-height: 1.45;
  text-align: left;
}
.auth-error svg, .auth-error :deep(svg) { flex: 0 0 auto; margin-top: 2px; }

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

@keyframes medical-glyph-float {
  0%, 100% { translate: 0 0; }
  50% { translate: 0 -7px; }
}
@keyframes medical-breathe {
  0%, 100% { transform: scale(.94); }
  50% { transform: scale(1.05); }
}

@media (max-width: 760px) {
  .auth-shell { padding: 16px 12px 20px; }
  .auth-card { height: min(820px, calc(100dvh - 64px)); min-height: 700px; }
  .tone-panel {
    width: 100%;
    height: 30%;
    bottom: auto;
    left: 0 !important;
    transition: top .8s cubic-bezier(.76, 0, .24, 1);
  }
  .auth-card.reversed .tone-panel { top: 70%; }
  .white-panel {
    width: 100%;
    height: 71%;
    top: 29%;
    bottom: 0;
    left: 0 !important;
    border-radius: 16px 16px 0 0;
    transition: top .8s cubic-bezier(.76, 0, .24, 1), border-radius .8s;
  }
  .auth-card.reversed .white-panel { top: 0; border-radius: 0 0 16px 16px; }
  .auth-brand { top: 12px; left: 16px !important; right: auto !important; font-size: 14px; }
  .auth-card.reversed .auth-brand { top: auto; bottom: 10px; right: 16px !important; left: auto !important; }
  .medical-illustration { --medical-travel: -140px; width: min(148px, 42%); top: 52%; }
  .medical-center { width: 50%; }
  .pulse-mark { width: 26px; height: 26px; }
  .pulse-mark :deep(svg) { width: 14px; height: 14px; }
  .badge-pill { width: 38px; height: 38px; border-radius: 14px; }
  .badge-pill :deep(svg) { width: 20px; height: 20px; }
  .badge-capsule { width: 32px; height: 32px; }
  .badge-capsule :deep(svg) { width: 16px; height: 16px; }
  .badge-kit { width: 36px; height: 36px; border-radius: 13px; }
  .badge-kit :deep(svg) { width: 18px; height: 18px; }
  .medical-tablet { display: none; }
  .tone-caption { bottom: 8px; left: 16px !important; font-size: 12px; letter-spacing: .04em; }
  .auth-card.reversed .tone-caption { bottom: auto; top: 12px; right: 16px; left: auto !important; }
  .form-content { width: min(340px, 88%); }
  .title-group { margin-bottom: 18px; }
  .title-group h1 { font-size: 28px; }
}

@media (prefers-reduced-motion: reduce) {
  .medical-glow,
  .medical-center :deep(svg),
  .medical-badge :deep(svg) { animation: none; }
  .tone-panel,
  .white-panel,
  .auth-brand,
  .tone-caption,
  .form-content,
  .medical-piece { transition-duration: 1ms; }
}
</style>
