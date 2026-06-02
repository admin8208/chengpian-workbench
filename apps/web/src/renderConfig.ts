export type RenderAspect = 'landscape' | 'portrait'

export function normalizeAspect(value: string | null | undefined): RenderAspect {
  return String(value || '').trim().toLowerCase() === 'portrait' ? 'portrait' : 'landscape'
}

export function aspectLabel(value: string | null | undefined) {
  return normalizeAspect(value) === 'portrait' ? '竖版' : '横版'
}

export function defaultDimensionsForAspect(value: string | null | undefined) {
  const aspect = normalizeAspect(value)
  return aspect === 'portrait'
    ? { aspect, width: 944, height: 1664 }
    : { aspect, width: 1664, height: 944 }
}
