import request from '../request'

export function listHealthMetricTypes() {
  return request.get('/api/health-metrics/types')
}

export function getHealthMetricTrend(patientId, metricType, range) {
  return request.get(`/api/patients/${patientId}/health-metrics/trend`, {
    params: { metricType, range },
  })
}
