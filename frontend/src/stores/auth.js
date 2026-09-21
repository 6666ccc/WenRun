import { computed } from 'vue'
import { defineStore } from 'pinia'
import { login as loginApi, logout as logoutApi } from '../api/modules/user'
import { setToken } from '../api/request'
import { resetAllAssistantRuntimes } from '../composables/useAssistant'

const USER_KEY = 'wenrun_user'
const ACTIVE_PATIENT_KEY = 'wenrun_active_patient'

function loadUser() {
  try {
    return JSON.parse(localStorage.getItem(USER_KEY) || 'null')
  } catch {
    return null
  }
}

function normalizePatients(data) {
  if (Array.isArray(data?.patients) && data.patients.length) {
    return data.patients.map((item) => ({
      patientId: item.patientId,
      patientNo: item.patientNo,
      name: item.name,
      relationType: item.relationType || 'SELF',
      isDefault: !!item.isDefault,
    }))
  }
  if (data?.patientId) {
    return [{
      patientId: data.patientId,
      relationType: 'SELF',
      isDefault: true,
      name: data.realName || data.username || '本人',
    }]
  }
  return []
}

function resolveActivePatientId(patients, fallback) {
  const saved = Number(localStorage.getItem(ACTIVE_PATIENT_KEY) || 0)
  if (saved && patients.some((item) => Number(item.patientId) === saved)) return saved
  const defaultPatient = patients.find((item) => item.isDefault) || patients[0]
  return defaultPatient?.patientId || fallback || null
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
      const patients = normalizePatients(data)
      const activePatientId = resolveActivePatientId(patients, data.patientId)
      if (activePatientId) localStorage.setItem(ACTIVE_PATIENT_KEY, String(activePatientId))
      else localStorage.removeItem(ACTIVE_PATIENT_KEY)
      this.saveUser({
        userId: data.userId,
        username: data.username,
        realName: data.realName,
        roleCode: data.roleCode,
        roleName: data.roleName,
        portalType: data.portalType,
        patientId: activePatientId,
        activePatientId,
        patients,
        staffId: data.staffId,
        roles: data.roles,
      })
    },
    setActivePatient(patientId) {
      const id = Number(patientId)
      const patients = this.user?.patients || []
      if (!id || !patients.some((item) => Number(item.patientId) === id)) return
      localStorage.setItem(ACTIVE_PATIENT_KEY, String(id))
      this.saveUser({
        ...this.user,
        activePatientId: id,
        patientId: id,
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
      localStorage.removeItem(ACTIVE_PATIENT_KEY)
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
    activePatientId: computed(() => store.user?.activePatientId || store.user?.patientId || null),
    patients: computed(() => store.user?.patients || []),
    login: (username, password) => store.login(username, password),
    setSession: (data) => store.setSession(data),
    setActivePatient: (patientId) => store.setActivePatient(patientId),
    logout: () => store.logout(),
    updateUser: (partial) => store.updateUser(partial),
  }
}
