import request from '../request'

export function getPatient(id) {
  return request.get(`/api/patients/${id}`)
}

export function updatePatient(id, data) {
  return request.put(`/api/patients/${id}`, data)
}
