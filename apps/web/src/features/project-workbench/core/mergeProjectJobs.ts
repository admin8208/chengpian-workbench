import type { Job } from '../../../api'

export function mergeProjectJobs(currentJobs: Job[], newJobs: Job[]) {
  const current = new Map(currentJobs.map((job) => [job.id, job]))
  for (const job of newJobs) current.set(job.id, job)
  return [...current.values()].sort((a, b) => {
    const ta = Date.parse(String(a.updated_at || '')) || 0
    const tb = Date.parse(String(b.updated_at || '')) || 0
    if (tb !== ta) return tb - ta
    return Number(b.id || 0) - Number(a.id || 0)
  })
}
