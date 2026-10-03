import request from '../request'

export const listPreferences = (patientId, page = 0) => request.get('/api/ai/memories', {
  params: { patientId, page, size: 50 },
})
export const updatePreference = (patientId, memoryId, body) => request.put(
  `/api/ai/memories/${encodeURIComponent(memoryId)}`, body, { params: { patientId } },
)
