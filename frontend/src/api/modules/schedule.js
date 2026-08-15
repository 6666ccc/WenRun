import request from '../request'

export function listSchedules(params) {
  return request.get('/api/schedules', { params })
}

export function getSchedule(id) {
  return request.get(`/api/schedules/${id}`)
}

export function createSchedule(data) {
  return request.post('/api/schedules', data)
}

export function updateSchedule(id, data) {
  return request.put(`/api/schedules/${id}`, data)
}
