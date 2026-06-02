import { http } from './http'
import type { Job } from './types'

export const pipelineApi = {
  startAutopilot: (projectId: number) => http<{ ok: boolean; jobs: Job[] }>(`/api/projects/${projectId}/autopilot`, { method: 'POST' }),
  continueAutopilot: (projectId: number) => http<{ ok: boolean; jobs: Job[] }>(`/api/projects/${projectId}/autopilot/continue`, { method: 'POST' }),
  rerunAutopilot: (projectId: number) => http<{ ok: boolean; jobs: Job[] }>(`/api/projects/${projectId}/autopilot/rerun`, { method: 'POST' }),
}
