/**
 * 仅登录前接口跳过 Token。/api/health 是健康检查，不能用 includes 误伤患者健康指标路径。
 */
export function shouldSkipAuth(url = '') {
  const path = String(url).split('?')[0]
  return path === '/api/health'
    || path.endsWith('/api/health')
    || path === '/api/auth/login'
    || path.endsWith('/api/auth/login')
    || path === '/api/auth/register'
    || path.endsWith('/api/auth/register')
}
