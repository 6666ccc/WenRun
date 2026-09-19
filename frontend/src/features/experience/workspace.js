/**
 * PC 端首页工作台：把患者服务路径映射为首页右侧抽屉。
 * 返回 null 表示当前路径不需要打开抽屉（首页本身或非工作台路径）。
 */
export function workspacePanelFor(path, params = {}) {
  if (path === '/registration') return { kind: 'registration' }
  if (path === '/user') return { kind: 'user' }
  if (path.startsWith('/registration/') && params?.id !== undefined) return { kind: 'record', id: String(params.id) }
  return null
}

export const WORKSPACE_TITLES = {
  registration: '预约挂号',
  record: '挂号详情',
  user: '个人中心',
}
