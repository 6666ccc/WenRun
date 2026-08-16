export function buildResumePayload(conversationId, interruptId, approved, params) {
  const payload = {
    conversationId,
    interruptId,
    approved,
  }
  if (params && Object.keys(params).length) {
    payload.params = params
  }
  return payload
}

export function interruptSummary(interrupt) {
  return interrupt?.summary || interrupt?.params?.summary || '请确认是否继续该操作。'
}
