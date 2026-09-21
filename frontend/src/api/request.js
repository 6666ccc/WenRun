/**
 * Axios 实例 + 拦截器
 * 基址通过 Vite proxy → localhost:8080
 */
import axios from 'axios'
import { shouldSkipAuth } from './authSkip'

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/+$/, '')

const request = axios.create({
  // 本地开发留空走 Vite 代理；部署到独立前端域名时可配置后端 origin。
  baseURL: API_BASE_URL,
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
request.interceptors.request.use((config) => {
  const skip = shouldSkipAuth(config.url)
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
    // Spring 业务异常默认仍以 HTTP 200 返回，真正的状态码在统一响应体中。
    if (body?.code === 401) {
      setToken(null)
      localStorage.removeItem('wenrun_user')
      if (typeof window !== 'undefined' && window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
      return Promise.reject(new Error(body.message || '登录已过期，请重新登录'))
    }
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
        if (typeof window !== 'undefined' && window.location.pathname !== '/login') {
          window.location.href = '/login'
        }
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
