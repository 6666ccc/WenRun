import { createRouter, createWebHistory } from 'vue-router'
import { useAuth } from '../stores'
import { homePath } from '../utils/portal'
import { isPatientPortal } from '../features/experience/mode'

const routes = [
  { path: '/', redirect: '/login' },
  { path: '/login', component: () => import('../views/Login.vue'), meta: { guest: true } },
  { path: '/mode-select', redirect: '/home', meta: { patient: true } },
  { path: '/home', component: () => import('../views/Home.vue'), meta: { patient: true } },
  { path: '/user', component: () => import('../views/User.vue'), meta: { patient: true } },
  { path: '/assistant', component: () => import('../views/Assistant.vue'), meta: { patient: true } },
  { path: '/registration', component: () => import('../views/Registration.vue'), meta: { patient: true } },
  { path: '/registration/:id', component: () => import('../views/RegistrationDetail.vue'), meta: { patient: true } },
  { path: '/department', component: () => import('../views/Department.vue'), meta: { patient: true } },
  { path: '/payment', component: () => import('../views/Payment.vue'), meta: { patient: true } },
  { path: '/payment/:id', component: () => import('../views/PaymentDetail.vue'), meta: { patient: true } },
  { path: '/:pathMatch(.*)*', redirect: '/login' },
]

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach((to) => {
  const { user, isAuthenticated } = useAuth()
  if (to.meta.guest && isAuthenticated.value) return homePath()
  if (!to.meta.guest && !isAuthenticated.value) return '/login'
  if (to.meta.patient && !isPatientPortal(user.value)) return '/login'
  return true
})

export default router
