import request from '../request'

export function listStaff(params) {
  return request.get('/api/staff', { params })
}

export function getStaff(id) {
  return request.get(`/api/staff/${id}`)
}

export function createStaff(data) {
  return request.post('/api/staff', data)
}

export function updateStaff(id, data) {
  return request.put(`/api/staff/${id}`, data)
}
