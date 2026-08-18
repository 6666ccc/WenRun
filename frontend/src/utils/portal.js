import { isPatientPortal, patientHomePath } from '../features/experience/mode'

/** 患者登录后的统一入口。旧版调用保留这个函数，避免影响外部引用。 */
export function homePath() {
  return patientHomePath()
}

export { isPatientPortal }
