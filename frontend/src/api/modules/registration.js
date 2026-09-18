import request from '../request'

export function listRegistrations(params) {
  return request.get('/api/registrations', { params })
}

export function listPendingRegistrations(params) {
  return request.get('/api/registrations/pending', { params })
}

export function createRegistration(data) {
  return request.post('/api/registrations', data)
}

export function cancelRegistration(id) {
  return request.post(`/api/registrations/${id}/cancel`)
}

export function rescheduleRegistration(id, scheduleId) {
  return request.put(`/api/registrations/${id}/schedule`, { scheduleId })
}
