import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api, type Job } from '../api/index'

/**
 * 适用于列表页/项目页的通用 job 操作执行器。
 * 不绑定某一个固定 job ref，而是在调用时传入 job id 和执行函数。
 */
export function useJobActionRunner() {
  const busy = ref(false)

  async function run(
    action: () => Promise<void>,
    opts?: { success?: string; error?: string; onError?: (error: Error) => void }
  ) {
    if (busy.value) return false
    busy.value = true
    try {
      await action()
      if (opts?.success) ElMessage.success(opts.success)
      return true
    } catch (e: any) {
      opts?.onError?.(e)
      ElMessage.error(e?.message ?? opts?.error ?? '任务操作失败')
      return false
    } finally {
      busy.value = false
    }
  }

  async function runJob(
    job: Job,
    action: 'pause' | 'resume' | 'cancel' | 'retry',
    opts?: {
      success?: string
      error?: string
      onSuccess?: (updatedJob: Job) => Promise<void> | void
      onError?: (error: Error) => void
    }
  ) {
    return run(
      async () => {
        let updatedJob: Job
        if (action === 'pause') updatedJob = await api.pauseJob(job.id)
        else if (action === 'resume') updatedJob = await api.resumeJob(job.id)
        else if (action === 'cancel') updatedJob = await api.cancelJob(job.id)
        else updatedJob = (await api.retryJob(job.id)).job
        await opts?.onSuccess?.(updatedJob)
      },
      {
        success: opts?.success,
        error: opts?.error,
        onError: opts?.onError,
      }
    )
  }

  return {
    busy,
    run,
    runJob,
  }
}
