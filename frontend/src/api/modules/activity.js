import request from '../request'

export function getActivityOptions() {
  return request.get('/api/activity/options')
}

export function getActivitySummary(patientId, range = 7) {
  return request.get(`/api/patients/${patientId}/activity/summary`, { params: { range } })
}

export function listExercises(patientId, limit = 20) {
  return request.get(`/api/patients/${patientId}/exercises`, { params: { limit } })
}

export function createExercise(patientId, data) {
  return request.post(`/api/patients/${patientId}/exercises`, data)
}

export function updateExercise(patientId, id, data) {
  return request.put(`/api/patients/${patientId}/exercises/${id}`, data)
}

export function deleteExercise(patientId, id) {
  return request.delete(`/api/patients/${patientId}/exercises/${id}`)
}

export function listSleepRecords(patientId, limit = 20) {
  return request.get(`/api/patients/${patientId}/sleep-records`, { params: { limit } })
}

export function createSleepRecord(patientId, data) {
  return request.post(`/api/patients/${patientId}/sleep-records`, data)
}

export function updateSleepRecord(patientId, id, data) {
  return request.put(`/api/patients/${patientId}/sleep-records/${id}`, data)
}

export function deleteSleepRecord(patientId, id) {
  return request.delete(`/api/patients/${patientId}/sleep-records/${id}`)
}
