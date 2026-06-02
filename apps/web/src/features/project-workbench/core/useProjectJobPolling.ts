import { type Ref } from 'vue'
import { api, type Job } from '../../../api'

type UseProjectJobPollingArgs = {
  projectJobs: Ref<Job[]>
  autopilotJobs: Ref<Job[]>
  info: Ref<string>
  refreshAssetsOnly: () => Promise<void>
  refreshSummaryOnly: () => Promise<void>
  load: () => Promise<void>
}

export function useProjectJobPolling(args: UseProjectJobPollingArgs) {
  let pollTimer: number | null = null
  let pollFailStreak = 0
  let pollInFlight = false

  function sortJobsByUpdatedDesc(rows: Job[]) {
    return [...rows].sort((a, b) => {
      const ta = Date.parse(String(a.updated_at || '')) || 0
      const tb = Date.parse(String(b.updated_at || '')) || 0
      if (tb !== ta) return tb - ta
      return Number(b.id || 0) - Number(a.id || 0)
    })
  }

  function syncAutopilotJobsFromProjectJobs() {
    args.autopilotJobs.value = sortJobsByUpdatedDesc(args.projectJobs.value)
      .filter((j) => ['queued', 'running', 'paused'].includes(String(j.status || '').trim().toLowerCase()) || j.kind === 'autopilot')
      .slice(0, 6)
  }

  function patchLocalJobState(updatedJob: Job) {
    const apply = (rows: Job[]) => rows.map((item) => (item.id === updatedJob.id ? updatedJob : item))
    args.projectJobs.value = sortJobsByUpdatedDesc(apply(args.projectJobs.value))
    args.autopilotJobs.value = sortJobsByUpdatedDesc(apply(args.autopilotJobs.value))
    syncAutopilotJobsFromProjectJobs()
  }

  function stopPolling() {
    if (pollTimer) window.clearTimeout(pollTimer)
    pollTimer = null
    pollInFlight = false
  }

  function nextPollDelay() {
    if (document.hidden) return 3000
    const hasRunning = args.projectJobs.value.some((j) => ['running', 'queued', 'paused'].includes(String(j.status || '').trim().toLowerCase()))
    return hasRunning ? 1500 : 2500
  }

  async function pollAutopilotJobs(tick: number) {
    const trackedJobs = args.projectJobs.value.filter((j) => ['queued', 'running', 'paused'].includes(String(j.status || '').trim().toLowerCase()))
    if (!trackedJobs.length || pollInFlight) return
    pollInFlight = true
    try {
      const ids = trackedJobs.map((j) => j.id)
      const updated: Job[] = []
      for (const id of ids) updated.push(await api.getJob(id))
      const currentMap = new Map(args.projectJobs.value.map((job) => [job.id, job]))
      for (const job of updated) currentMap.set(job.id, job)
      args.projectJobs.value = sortJobsByUpdatedDesc([...currentMap.values()])
      syncAutopilotJobsFromProjectJobs()
      pollFailStreak = 0
      if (args.info.value.startsWith('连接后端失败')) args.info.value = ''
      if (tick % 4 === 0) {
        await args.refreshAssetsOnly()
        await args.refreshSummaryOnly()
      }
      const allDone = updated.every((j) => j.status === 'done' || j.status === 'failed' || j.status === 'cancelled' || j.status === 'paused')
      if (allDone) {
        stopPolling()
        await args.load()
        return
      }
    } catch {
      pollFailStreak += 1
      if (pollFailStreak >= 3) args.info.value = '连接后端失败，正在重试…（如果持续出现，请检查 API/Worker 是否启动）'
    } finally {
      pollInFlight = false
    }
  }

  function startPolling() {
    stopPolling()
    let tick = 0
    const schedule = () => {
      pollTimer = window.setTimeout(async () => {
        tick += 1
        await pollAutopilotJobs(tick)
        if (pollTimer !== null && args.projectJobs.value.some((j) => ['queued', 'running', 'paused'].includes(String(j.status || '').trim().toLowerCase()))) schedule()
      }, nextPollDelay())
    }
    schedule()
  }

  function refreshPollingByCurrentJobs() {
    const hasActive = args.projectJobs.value.some((j) => ['queued', 'running', 'paused'].includes(String(j.status || '').trim().toLowerCase()))
    if (hasActive) startPolling()
    else stopPolling()
  }

  return {
    sortJobsByUpdatedDesc,
    syncAutopilotJobsFromProjectJobs,
    patchLocalJobState,
    stopPolling,
    startPolling,
    refreshPollingByCurrentJobs,
  }
}
