import { ref, type Ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api, type Job } from '../api/index'

/**
 * Job 操作 composable
 * 提供统一的 pause/resume/cancel/retry 操作
 */
export function useJobActions(
  job: Ref<Job | null>,
  options?: {
    onUpdate?: (updatedJob: Job) => void
    onSuccess?: (action: string) => void
    onError?: (action: string, error: Error) => void
  }
) {
  const busy = ref(false)

  function setJob(updatedJob: Job) {
    job.value = updatedJob
    options?.onUpdate?.(updatedJob)
  }

  async function pause() {
    if (!job.value?.id || busy.value) return
    busy.value = true
    try {
      const updated = await api.pauseJob(job.value.id)
      setJob(updated)
      ElMessage.success('任务已暂停')
      options?.onSuccess?.('pause')
    } catch (e: any) {
      ElMessage.error(e?.message ?? '暂停任务失败')
      options?.onError?.('pause', e)
    } finally {
      busy.value = false
    }
  }

  async function resume() {
    if (!job.value?.id || busy.value) return
    busy.value = true
    try {
      const updated = await api.resumeJob(job.value.id)
      setJob(updated)
      ElMessage.success('任务已继续执行')
      options?.onSuccess?.('resume')
    } catch (e: any) {
      ElMessage.error(e?.message ?? '继续任务失败')
      options?.onError?.('resume', e)
    } finally {
      busy.value = false
    }
  }

  async function cancel() {
    if (!job.value?.id || busy.value) return
    busy.value = true
    try {
      const updated = await api.cancelJob(job.value.id)
      setJob(updated)
      ElMessage.success('任务已取消')
      options?.onSuccess?.('cancel')
    } catch (e: any) {
      ElMessage.error(e?.message ?? '取消任务失败')
      options?.onError?.('cancel', e)
    } finally {
      busy.value = false
    }
  }

  async function retry() {
    if (!job.value?.id || busy.value) return
    busy.value = true
    try {
      const res = await api.retryJob(job.value.id)
      setJob(res.job)
      ElMessage.success('已重新提交任务')
      options?.onSuccess?.('retry')
    } catch (e: any) {
      ElMessage.error(e?.message ?? '重新提交任务失败')
      options?.onError?.('retry', e)
    } finally {
      busy.value = false
    }
  }

  return {
    busy,
    pause,
    resume,
    cancel,
    retry,
  }
}
