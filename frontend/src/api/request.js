/**
 * Axios 实例 + 拦截器
 * 基址通过 Vite proxy → localhost:8080
 */
import axios from 'axios'

const request = axios.create({
  baseURL: '',           // Vite proxy handles /api → localhost:8080
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' },
})

/* ---------- Token 存取 ---------- */
const TOKEN_KEY = 'wenrun_token'

export function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token) {
  if (token) {
    localStorage.setItem(TOKEN_KEY, token)
  } else {
    localStorage.removeItem(TOKEN_KEY)
  }
}

/* ---------- 请求拦截器 ---------- */
const SKIP_AUTH = ['/api/health', '/api/auth/login', '/api/auth/register']

request.interceptors.request.use((config) => {
  const skip = SKIP_AUTH.some((p) => config.url?.includes(p))
  if (!skip) {
    const token = getToken()
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
      config.headers['X-Token'] = token
    }
  }
  return config
})

/* ---------- 响应拦截器 ---------- */
request.interceptors.response.use(
  (res) => {
    const body = res.data
    if (body && body.code === 200) {
      return body.data
    }
    return Promise.reject(new Error(body?.message || '请求失败'))
  },
  (err) => {
    if (err.response) {
      const { status, data } = err.response
      if (status === 401) {
        // Token 失效 → 清理并跳转登录
        setToken(null)
        localStorage.removeItem('wenrun_user')
        window.location.href = '/login'
        return Promise.reject(new Error('登录已过期，请重新登录'))
      }
      const msg = data?.message || `服务器错误 (${status})`
      return Promise.reject(new Error(msg))
    }
    if (err.code === 'ECONNABORTED') {
      return Promise.reject(new Error('请求超时'))
    }
    return Promise.reject(new Error('网络异常，请检查网络连接'))
  },
)

export default request
