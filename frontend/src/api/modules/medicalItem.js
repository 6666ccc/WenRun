import request from '../request'

export function listMedicalItems(params) {
  return request.get('/api/medical-items', { params })
}

export function getMedicalItem(id) {
  return request.get(`/api/medical-items/${id}`)
}
