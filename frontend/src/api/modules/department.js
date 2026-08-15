import request from '../request'

export function listDepts(params) {
  return request.get('/api/depts', { params })
}

export function getDept(id) {
  return request.get(`/api/depts/${id}`)
}

export function createDept(data) {
  return request.post('/api/depts', data)
}

export function updateDept(id, data) {
  return request.put(`/api/depts/${id}`, data)
}
