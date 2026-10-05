import request from '../request'

export function listSchedules(params) {
  return request.get('/api/schedules', { params })
}
