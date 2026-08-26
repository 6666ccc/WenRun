import { computed } from 'vue'
import { defineStore } from 'pinia'
import { login as loginApi, logout as logoutApi } from '../api/modules/user'
import { setToken } from '../api/request'
import { resetAllAssistantRuntimes } from '../composables/useAssistant'

const USER_KEY = 'wenrun_user'

function loadUser() {
  try {
    return JSON.parse(localStorage.getItem(USER_KEY) || 'null')
  } catch {
    return null
  }
}

export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: loadUser(),
    loading: false,
  }),
  actions: {
    saveUser(user) {
      this.user = user
      if (user) localStorage.setItem(USER_KEY, JSON.stringify(user))
      else localStorage.removeItem(USER_KEY)
    },
    setSession(data) {
      setToken(data.token)
      this.saveUser({
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
    },
    async login(username, password) {
      this.loading = true
      try {
        const data = await loginApi({ username, password })
        this.setSession(data)
        return { success: true }
      } catch (error) {
        return { success: false, error: error.message }
      } finally {
        this.loading = false
      }
    },
    async logout() {
      try { await logoutApi() } catch { /* 本地状态仍需清理 */ }
      resetAllAssistantRuntimes()
      setToken(null)
      this.saveUser(null)
    },
    updateUser(partial) {
      this.saveUser({ ...this.user, ...partial })
    },
  },
})

export function useAuth() {
  const store = useAuthStore()
  return {
    state: computed(() => store.$state),
    user: computed(() => store.user),
    loading: computed(() => store.loading),
    token: computed(() => store.user && localStorage.getItem('wenrun_token')),
    isAuthenticated: computed(() => !!store.user && !!localStorage.getItem('wenrun_token')),
    login: (username, password) => store.login(username, password),
    setSession: (data) => store.setSession(data),
    logout: () => store.logout(),
    updateUser: (partial) => store.updateUser(partial),
  }
}
