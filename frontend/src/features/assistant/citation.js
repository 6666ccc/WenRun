export function sourceLabel(source) {
  if (!source) return '来源'
  if (source.kind === 'tool' || source.toolName) {
    return source.toolName || '业务查询'
  }
  return source.title || source.documentId || '资料'
}

export function sourceLocation(source) {
  if (!source) return ''
  if (source.page != null) return `第 ${source.page} 页`
  if (source.section) return source.section
  if (source.queryTime) return source.queryTime
  return ''
}

export function sourceExcerpt(source) {
  return source?.excerpt || source?.summary || ''
}
