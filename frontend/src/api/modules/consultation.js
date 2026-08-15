import request from '../request'

/* ---------- 就诊 ---------- */
export function listVisits(params) {
  return request.get('/api/visits', { params })
}

export function getVisit(id) {
  return request.get(`/api/visits/${id}`)
}

export function startVisit(registrationId) {
  return request.post(`/api/visits/start/${registrationId}`)
}

export function updateVisit(id, data) {
  return request.put(`/api/visits/${id}`, data)
}

/* ---------- 处方 ---------- */
export function listPrescriptions(params) {
  return request.get('/api/prescriptions', { params })
}

export function getPrescription(id) {
  return request.get(`/api/prescriptions/${id}`)
}

export function createPrescription(data) {
  return request.post('/api/prescriptions', data)
}

export function cancelPrescription(id) {
  return request.post(`/api/prescriptions/${id}/cancel`)
}

/* ---------- 检查申请 ---------- */
export function listExamRequests(params) {
  return request.get('/api/exam-requests', { params })
}

export function createExamRequest(data) {
  return request.post('/api/exam-requests', data)
}
