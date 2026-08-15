import request from '../request'

export function listDrugs(params) {
  return request.get('/api/drugs', { params })
}

export function getDrug(id) {
  return request.get(`/api/drugs/${id}`)
}

export function createDrug(data) {
  return request.post('/api/drugs', data)
}

export function updateDrug(id, data) {
  return request.put(`/api/drugs/${id}`, data)
}
