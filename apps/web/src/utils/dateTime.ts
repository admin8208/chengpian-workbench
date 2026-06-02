function normalizeIsoLikeUtc(value: string) {
  const text = String(value || '').trim()
  if (!text) return ''
  if (/[zZ]$|[+-]\d{2}:?\d{2}$/.test(text)) return text
  if (/^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(\.\d+)?$/.test(text)) return `${text.replace(' ', 'T')}Z`
  return text
}

export function formatDateTime(value: string | number | Date | null | undefined) {
  if (value == null || value === '') return ''
  const normalized = typeof value === 'string' ? normalizeIsoLikeUtc(value) : value
  const date = normalized instanceof Date ? normalized : new Date(normalized)
  if (Number.isNaN(date.getTime())) return String(value)
  return new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).format(date)
}

export function formatTime(value: string | number | Date | null | undefined) {
  if (value == null || value === '') return ''
  const normalized = typeof value === 'string' ? normalizeIsoLikeUtc(value) : value
  const date = normalized instanceof Date ? normalized : new Date(normalized)
  if (Number.isNaN(date.getTime())) return String(value)
  return new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).format(date)
}
