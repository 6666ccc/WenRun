export const MODE_AGENT = 'agent'
export const MODE_CLASSIC = 'classic'
export const MODE_STORAGE_KEY = 'wenrun_patient_mode'

export function normalizeMode(value) {
  return value === MODE_CLASSIC ? MODE_CLASSIC : MODE_AGENT
}

export function readMode(storage = localStorage) {
  return normalizeMode(storage.getItem(MODE_STORAGE_KEY))
}

export function writeMode(mode, storage = localStorage) {
  const nextMode = normalizeMode(mode)
  storage.setItem(MODE_STORAGE_KEY, nextMode)
  return nextMode
}

export function patientHomePath() {
  return '/home'
}

export function isPatientPortal(user) {
  return !user?.portalType || user.portalType === 'patient'
}
