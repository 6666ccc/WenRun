import { isPatientPortal, patientHomePath } from '../features/experience/mode'

/** 患者登录后选择使用新版或传统版。 */
export function homePath() {
  return patientHomePath()
}

export { isPatientPortal }
