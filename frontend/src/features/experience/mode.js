export function patientHomePath() {
  return '/home'
}

export function isPatientPortal(user) {
  return !user?.portalType || user.portalType === 'patient'
}

/** 旧的 /assistant 路径统一并入首页，保留 prompt / preview 等 query。 */
export function assistantRedirect(to) {
  return { path: '/home', query: { ...(to?.query || {}) } }
}
