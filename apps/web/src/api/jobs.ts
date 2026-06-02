import { http } from './http'
import type { Job } from './types'

export const jobsApi = {
  getJob: (jobId: number) => http<Job>(`/api/jobs/${jobId}`),
  listJobs: (limit = 100, options: { projectId?: number } = {}) => {
    const params = new URLSearchParams({ limit: String(limit) })
    if (options.projectId && options.projectId > 0) params.set('project_id', String(options.projectId))
    return http<Job[]>(`/api/jobs?${params.toString()}`)
  },
  cancelJob: (jobId: number) => http<Job>(`/api/jobs/${jobId}/cancel`, { method: 'POST' }),
  pauseJob: (jobId: number) => http<Job>(`/api/jobs/${jobId}/pause`, { method: 'POST' }),
  resumeJob: (jobId: number) => http<Job>(`/api/jobs/${jobId}/resume`, { method: 'POST' }),
  retryJob: (jobId: number) => http<{ job: Job }>(`/api/jobs/${jobId}/retry`, { method: 'POST' }),
  deleteJob: (jobId: number) => http<{ ok: boolean }>(`/api/jobs/${jobId}`, { method: 'DELETE' }),
}
