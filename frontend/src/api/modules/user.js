import request from '../request'

/** 登录 */
export function login(data) {
  return request.post('/api/auth/login', data)
}

/** 患者自助注册 */
export function register(data) {
  return request.post('/api/auth/register', data)
}

/** 退出登录 */
export function logout() {
  return request.post('/api/auth/logout')
}

/** 更新个人资料 */
export function updateProfile(data) {
  return request.put('/api/user/profile', data)
}
