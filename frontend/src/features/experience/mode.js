export function patientHomePath() {
  return '/home'
}

export function isPatientPortal(user) {
  return !user?.portalType || user.portalType === 'patient'
}
