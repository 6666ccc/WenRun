import { computed, reactive, readonly } from 'vue'
import { login as loginApi, logout as logoutApi } from '../api/modules/user'
import { setToken } from '../api/request'

const USER_KEY = 'wenrun_user'

function loadUser() {
  try {
    return JSON.parse(localStorage.getItem(USER_KEY) || 'null')
  } catch {
    return null
  }
}

const state = reactive({
  user: loadUser(),
  loading: false,
})

function saveUser(user) {
  state.user = user
  if (user) localStorage.setItem(USER_KEY, JSON.stringify(user))
  else localStorage.removeItem(USER_KEY)
}

function setSession(data) {
  setToken(data.token)
  saveUser({
    userId: data.userId,
    username: data.username,
    realName: data.realName,
    roleCode: data.roleCode,
    roleName: data.roleName,
    portalType: data.portalType,
    patientId: data.patientId,
    staffId: data.staffId,
    roles: data.roles,
  })
}

async function login(username, password) {
  state.loading = true
  try {
    const data = await loginApi({ username, password })
    setSession(data)
    return { success: true }
  } catch (error) {
    return { success: false, error: error.message }
  } finally {
    state.loading = false
  }
}

async function logout() {
  try { await logoutApi() } catch { /* 本地状态仍需清理 */ }
  setToken(null)
  saveUser(null)
}

function updateUser(partial) {
  saveUser({ ...state.user, ...partial })
}

export function useAuth() {
  return {
    state: readonly(state),
    user: computed(() => state.user),
    loading: computed(() => state.loading),
    token: computed(() => state.user && localStorage.getItem('wenrun_token')),
    isAuthenticated: computed(() => !!state.user && !!localStorage.getItem('wenrun_token')),
    login,
    setSession,
    logout,
    updateUser,
  }
}
