import { http } from './http'
import type { Job, Project } from './types'

export const baselineApi = {
  prepareProjectScript: (id: number) => http<{ job: Job }>(`/api/projects/${id}/script`, { method: 'POST', timeoutMs: 600000 }),
  confirmProjectScript: (id: number, script?: string) => http<Project>(`/api/projects/${id}/script/confirm`, { method: 'POST', body: JSON.stringify({ script }) }),
}
