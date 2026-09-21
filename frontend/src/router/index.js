import { createRouter, createWebHistory } from 'vue-router'
import { useAuth } from '../stores'
import { homePath } from '../utils/portal'
import { assistantRedirect, isPatientPortal, userArchiveRedirect } from '../features/experience/mode'

const routes = [
  { path: '/', redirect: '/login' },
  { path: '/login', component: () => import('../views/Login.vue'), meta: { guest: true } },
  { path: '/mode-select', redirect: '/home', meta: { patient: true } },
  // 首页与挂号共用工作台：PC 上挂号以抽屉叠在聊天之上，移动端仍是独立页面。个人档案为独立全页。
  { path: '/home', component: () => import('../views/PatientWorkspace.vue'), meta: { patient: true } },
  { path: '/assistant', redirect: assistantRedirect },
  { path: '/archive', component: () => import('../views/PatientArchive.vue'), meta: { patient: true } },
  { path: '/user', redirect: userArchiveRedirect, meta: { patient: true } },
  { path: '/registration', component: () => import('../views/PatientWorkspace.vue'), meta: { patient: true } },
  { path: '/registration/:id', component: () => import('../views/PatientWorkspace.vue'), meta: { patient: true } },
  { path: '/:pathMatch(.*)*', redirect: '/login' },
]

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach((to) => {
  if (import.meta.env.DEV && to.path === '/home' && to.query.preview === '1') return true
  const { user, isAuthenticated } = useAuth()
  if (to.meta.guest && isAuthenticated.value) return homePath()
  if (!to.meta.guest && !isAuthenticated.value) return '/login'
  if (to.meta.patient && !isPatientPortal(user.value)) return '/login'
  return true
})

export default router
