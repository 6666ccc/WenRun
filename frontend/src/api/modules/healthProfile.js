import request from '../request'

export function getHealthProfile(patientId) {
  return request.get(`/api/patients/${patientId}/health-profile`)
}

export function createHealthProfile(patientId, data) {
  return request.post(`/api/patients/${patientId}/health-profile`, data)
}

export function updateHealthProfile(patientId, data) {
  return request.put(`/api/patients/${patientId}/health-profile`, data)
}
