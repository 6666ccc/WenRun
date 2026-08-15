import request from '../request'

export function listCharges(params) {
  return request.get('/api/charges', { params })
}

export function listPendingCharges() {
  return request.get('/api/charges/pending')
}

export function getCharge(id) {
  return request.get(`/api/charges/${id}`)
}

export function createChargeFromVisit(visitId) {
  return request.post(`/api/charges/from-visit/${visitId}`)
}

export function payCharge(id, data) {
  return request.post(`/api/charges/${id}/pay`, data)
}
