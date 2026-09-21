import request from '../request'

export function listRegistrations(params) {
  const { patientId, ...rest } = params || {}
  if (patientId) {
    return request.get(`/api/patients/${patientId}/registrations`, { params: rest })
  }
  return request.get('/api/registrations', { params: rest })
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
