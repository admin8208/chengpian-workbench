import { computed, type Ref } from 'vue'
import type { Job } from '../api/index'

const ACTIVE_JOB_STATUSES = ['queued', 'running', 'paused']

/**
 * Job 状态判断 composable
 * 提供标准化的 Job 状态计算属性
 */
export function useJobStatus(job: Ref<Job | null>) {
  const statusCode = computed(() => String(job.value?.status || '').trim().toLowerCase())

  const isActive = computed(() => ACTIVE_JOB_STATUSES.includes(statusCode.value))
  const isQueued = computed(() => statusCode.value === 'queued')
  const isRunning = computed(() => statusCode.value === 'running')
  const isPaused = computed(() => statusCode.value === 'paused')
  const isDone = computed(() => statusCode.value === 'done')
  const isFailed = computed(() => statusCode.value === 'failed')
  const isCancelled = computed(() => statusCode.value === 'cancelled')

  const canPause = computed(() => isQueued.value || isRunning.value)
  const canResume = computed(() => isPaused.value)
  const canCancel = computed(() => isActive.value)
  const canRetry = computed(() => isFailed.value || isCancelled.value)

  const progress = computed(() => Number(job.value?.progress || 0))
  const message = computed(() => String(job.value?.message || '').trim())

  const statusLabel = computed(() => {
    if (!job.value) return ''
    switch (statusCode.value) {
      case 'queued': return '排队中'
      case 'running': return '执行中'
      case 'paused': return '已暂停'
      case 'done': return '已完成'
      case 'failed': return '失败'
      case 'cancelled': return '已取消'
      default: return statusCode.value
    }
  })

  const statusTone = computed(() => {
    switch (statusCode.value) {
      case 'done': return 'ok'
      case 'running': return 'run'
      case 'failed': return 'bad'
      case 'paused': return 'warn'
      default: return ''
    }
  })

  return {
    statusCode,
    isActive,
    isQueued,
    isRunning,
    isPaused,
    isDone,
    isFailed,
    isCancelled,
    canPause,
    canResume,
    canCancel,
    canRetry,
    progress,
    message,
    statusLabel,
    statusTone,
  }
}
