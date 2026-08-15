import request from '../request'

export function listPatients(params) {
  return request.get('/api/patients', { params })
}

export function getPatient(id) {
  return request.get(`/api/patients/${id}`)
}

export function createPatient(data) {
  return request.post('/api/patients', data)
}

export function updatePatient(id, data) {
  return request.put(`/api/patients/${id}`, data)
}
