import type { Ref } from 'vue'
import type { Job } from '../../../api'
import { useJobActionRunner } from '../../../composables/useJobActionRunner'

type UseProjectTaskActionsArgs = {
  err: Ref<string>
  continueAutopilot: () => Promise<void>
  loadProjectJobs: (limit?: number) => Promise<void>
  refreshProjectTaskState: () => Promise<void>
  refreshPollingByCurrentJobs: () => void
  patchLocalJobState: (job: Job) => void
  startPolling: () => void
  stopPolling: () => void
}

export function useProjectTaskActions(args: UseProjectTaskActionsArgs) {
  const { busy, runJob } = useJobActionRunner()

  async function pauseTask(job: Job) {
    args.err.value = ''
    await runJob(job, 'pause', {
      error: '暂停任务失败',
      onSuccess: async (updated) => {
        args.stopPolling()
        args.patchLocalJobState(updated)
        await args.refreshProjectTaskState()
      },
      onError: (e) => {
        args.err.value = e?.message ?? String(e)
      },
    })
    if (!busy.value) args.refreshPollingByCurrentJobs()
  }

  async function resumeTask(job: Job) {
    args.err.value = ''
    await runJob(job, 'resume', {
      error: '继续任务失败',
      onSuccess: async (updated) => {
        args.stopPolling()
        args.patchLocalJobState(updated)
        await args.refreshProjectTaskState()
      },
      onError: (e) => {
        args.err.value = e?.message ?? String(e)
      },
    })
    if (!busy.value) args.refreshPollingByCurrentJobs()
  }

  async function cancelTask(job: Job) {
    args.err.value = ''
    await runJob(job, 'cancel', {
      error: '取消任务失败',
      onSuccess: async (updated) => {
        args.stopPolling()
        args.patchLocalJobState(updated)
        await args.refreshProjectTaskState()
      },
      onError: (e) => {
        args.err.value = e?.message ?? String(e)
      },
    })
    if (!busy.value) args.refreshPollingByCurrentJobs()
  }

  async function retryTask(job: Job) {
    args.err.value = ''
    await runJob(job, 'retry', {
      error: '重试任务失败',
      onSuccess: async () => {
        await args.refreshProjectTaskState()
        args.startPolling()
      },
      onError: (e) => {
        args.err.value = e?.message ?? String(e)
      },
    })
  }

  return {
    taskActionBusy: busy,
    pauseTask,
    resumeTask,
    cancelTask,
    retryTask,
  }
}
