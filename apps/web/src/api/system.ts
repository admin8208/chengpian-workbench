import { http } from './http'
import type { Health } from './types'

export const systemApi = {
  health: (options: { probe?: boolean } = {}) => http<Health>(`/api/health${options.probe ? '?probe=true' : ''}`),
}
