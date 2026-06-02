import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'

import { api, type FeedConnectionState, type Job, type JobCenterFeed, type JobCenterItem } from '../../api'
import { useJobActionRunner } from '../../composables/useJobActionRunner'

export type VisibleEntry = JobCenterItem

const statusOptions = [
  { value: 'all', label: '全部' },
  { value: 'active', label: '进行中' },
  { value: 'failed', label: '失败' },
  { value: 'done', label: '已完成' },
  { value: 'cancelled', label: '已取消' },
] as const

const taskScopeOptions = [
  { value: 'project', label: '项目任务' },
  { value: 'all', label: '全部任务' },
] as const

const JOB_CENTER_LIMIT = 50
const JOB_CENTER_FALLBACK_POLL_INTERVAL = 15000

export function useJobsView() {
  const router = useRouter()
  const feed = ref<JobCenterFeed | null>(null)
  const jobs = ref<Job[]>([])
  const expandedChainIds = ref<number[]>([])
  const loading = ref(true)
  const err = ref('')
  const filterStatus = ref<'all' | 'active' | 'failed' | 'done' | 'cancelled'>('all')
  const taskScope = ref<'project' | 'all'>('project')
  const deletingProject = ref(false)
  const projectionRebuilding = ref(false)
  const selectionMode = ref(false)
  const selectedEntryKeys = ref<string[]>([])
  const bulkDeletingJobs = ref(false)
  const feedConnectionState = ref<FeedConnectionState>('connecting')
  const runtimeWarning = ref('')
  let pollTimer: ReturnType<typeof setInterval> | null = null

  const selectedProjectId = computed(() => {
    const raw = router.currentRoute.value.query.projectId
    const first = Array.isArray(raw) ? raw[0] : raw
    const value = Number(first || 0)
    return Number.isFinite(value) && value > 0 ? value : 0
  })

  const { busy: jobActionBusy, run: runJobAction, runJob } = useJobActionRunner()

  const statusOptionMap = Object.fromEntries(statusOptions.map((item) => [item.value, item.label]))
  const taskScopeOptionMap = Object.fromEntries(taskScopeOptions.map((item) => [item.value, item.label]))

  function isProjectMissingError(error: unknown) {
    const message = String((error as any)?.message ?? error ?? '').trim()
    return message === '请求的资源不存在' || message.includes('项目不存在')
  }

  function normalizeStatus(status: string | null | undefined) {
    return String(status || '').trim().toLowerCase()
  }

  const visibleEntries = computed(() => feed.value?.items || [])
  const visibleJobs = computed(() => jobs.value)
  const visibleJobMap = computed(() => new Map(visibleJobs.value.map((job) => [Number(job.id), job])))

  function canDeleteEntry(entry: VisibleEntry) {
    return entry.is_deletable
  }

  const deletableVisibleEntries = computed(() => visibleEntries.value.filter(canDeleteEntry))
  const selectedEntries = computed(() => visibleEntries.value.filter((entry) => selectedEntryKeys.value.includes(entry.entry_key)))
  const selectedDeletableEntries = computed(() => selectedEntries.value.filter(canDeleteEntry))
  const allDeletableVisibleSelected = computed(() => {
    const keys = deletableVisibleEntries.value.map((entry) => entry.entry_key)
    return keys.length > 0 && keys.every((key) => selectedEntryKeys.value.includes(key))
  })

  function setSelectionMode(next: boolean) {
    selectionMode.value = next
    if (!next) selectedEntryKeys.value = []
  }

  function isSelectedEntry(entry: VisibleEntry) {
    return selectedEntryKeys.value.includes(entry.entry_key)
  }

  function toggleEntrySelection(entry: VisibleEntry) {
    if (!selectionMode.value || bulkDeletingJobs.value || !canDeleteEntry(entry)) return
    selectedEntryKeys.value = isSelectedEntry(entry)
      ? selectedEntryKeys.value.filter((key) => key !== entry.entry_key)
      : [...selectedEntryKeys.value, entry.entry_key]
  }

  function selectAllVisibleEntries() {
    selectedEntryKeys.value = deletableVisibleEntries.value.map((entry) => entry.entry_key)
  }

  function clearSelectedEntries() {
    selectedEntryKeys.value = []
  }

  const stats = computed(() => feed.value?.stats || { all: 0, active: 0, failed: 0, done: 0, cancelled: 0 })
  let loadPromise: Promise<void> | null = null
  let loadKey = ''
  let loadSeq = 0

  async function load() {
    const key = `${taskScope.value}:${filterStatus.value}:${selectedProjectId.value}`
    if (loadPromise && loadKey === key) return loadPromise
    const seq = ++loadSeq
    loadKey = key
    err.value = ''
    loading.value = true
    loadPromise = (async () => {
      try {
        const nextFeed = await api.getJobCenterFeed({
          limit: JOB_CENTER_LIMIT,
          scope: taskScope.value,
          status: filterStatus.value,
          projectId: selectedProjectId.value || undefined,
        })
        if (seq !== loadSeq) return
        feed.value = nextFeed
        projectionRebuilding.value = Boolean(nextFeed.rebuilding)
        jobs.value = visibleEntries.value.map((entry) => ({
          id: entry.job_id,
          kind: entry.job_kind,
          project_id: entry.project_id,
          root_job_id: entry.root_job_id,
          project_title: entry.project_title,
          status: entry.status,
          progress: entry.progress,
          message: entry.message_label,
          error_code: entry.error_code,
          blocking_component: entry.blocking_component,
          recommended_action: entry.recommended_action,
          payload_json: '{}',
          created_at: entry.updated_at,
          updated_at: entry.updated_at,
        })) as Job[]
        selectedEntryKeys.value = selectedEntryKeys.value.filter((key) => visibleEntries.value.some((entry) => entry.entry_key === key))
        expandedChainIds.value = expandedChainIds.value.filter((rootId) => visibleEntries.value.some((entry) => entry.entry_type === 'chain' && Number(entry.root_job_id || 0) === rootId))
      } catch (e: any) {
        if (seq === loadSeq) err.value = e?.message ?? String(e)
      } finally {
        if (seq === loadSeq) loading.value = false
        if (loadKey === key) {
          loadPromise = null
          loadKey = ''
        }
      }
    })()
    return loadPromise
  }

  watch([taskScope, filterStatus, selectedProjectId], () => {
    load().catch((e) => {
      err.value = e?.message ?? String(e)
    })
  })

  function projectLabel(job: Job) {
    const projectId = Number(job.project_id || 0)
    return job.project_title || (projectId > 0 ? `项目 #${projectId}` : '系统任务')
  }

  function diagnosticsConfig(_job: Job) {
    return null as any
  }

  function isChainExpanded(rootId: number) {
    return expandedChainIds.value.includes(rootId)
  }

  function toggleChain(rootId: number) {
    expandedChainIds.value = isChainExpanded(rootId)
      ? expandedChainIds.value.filter((id) => id !== rootId)
      : [...expandedChainIds.value, rootId]
  }

  function openProject(job: Job) {
    const entry = visibleEntries.value.find((item) => item.job_id === job.id)
    if (!entry) return
    router.push({ path: entry.project_open_path })
  }

  async function openFinal(job: Job) {
    const projectId = Number(job.project_id || 0)
    if (!projectId) return
    try {
      const fin = await api.finalExport(projectId)
      if (!fin.exists || !fin.url) {
        ElMessage.info(`项目《${job.project_title || `#${projectId}` }》当前还没有最终成片文件。`)
        return
      }
      window.open(fin.url, '_blank')
    } catch (e: any) {
      ElMessage.error(e?.message ?? String(e))
    }
  }

  function hasFinalOutput(job: Job) {
    const entry = visibleEntries.value.find((item) => item.job_id === job.id)
    return Boolean(entry?.project_final_exists)
  }

  function statusTagType(status: string) {
    const normalized = normalizeStatus(status)
    if (normalized === 'failed' || normalized === 'cancelled') return 'danger'
    if (normalized === 'done') return 'success'
    if (normalized === 'paused') return 'warning'
    return 'info'
  }

  async function pauseJob(job: Job) {
    await runJob(job, 'pause', { error: '暂停任务失败', onSuccess: async () => { await load() } })
  }

  async function resumeJob(job: Job) {
    await runJob(job, 'resume', { error: '继续任务失败', onSuccess: async () => { await load() } })
  }

  async function cancelJob(job: Job) {
    await runJob(job, 'cancel', { error: '取消任务失败', onSuccess: async () => { await load() } })
  }

  async function retryJob(job: Job) {
    await runJob(job, 'retry', { error: '重试任务失败', onSuccess: async () => { await load() } })
  }

  async function deleteJob(job: Job) {
    await runJobAction(async () => {
      await ElMessageBox.confirm(`确定删除任务 #${job.id}？\n\n这只会删除这条任务记录及其附属输出，不会删除项目内容。`, '删除任务确认', { type: 'warning' })
      await api.deleteJob(job.id)
      await load()
      ElMessage.success(`已删除任务 #${job.id}。`)
    }, { error: '删除任务失败' })
  }

  async function deleteSelectedJobs() {
    if (bulkDeletingJobs.value || !selectedDeletableEntries.value.length) return
    const entries = [...selectedDeletableEntries.value]
    const jobsToDelete = Array.from(new Map(entries.map((entry) => [entry.job_id, entry.job_id])).values())
    if (!jobsToDelete.length) return
    try {
      await ElMessageBox.confirm(
        `确定批量删除 ${entries.length} 个任务视图？\n\n将删除 ${jobsToDelete.length} 条任务记录；这只会删除任务记录及其附属输出，不会删除项目内容。\n该操作无法恢复。`,
        '批量删除任务确认',
        { type: 'warning' }
      )
    } catch {
      return
    }
    bulkDeletingJobs.value = true
    try {
      const successIds: number[] = []
      const failed: Array<{ id: number, reason: string }> = []
      for (const jobId of jobsToDelete) {
        try {
          await api.deleteJob(jobId)
          successIds.push(jobId)
        } catch (e: any) {
          failed.push({ id: jobId, reason: e?.message ?? String(e) })
        }
      }
      if (successIds.length) {
        ElMessage.success(`已删除 ${successIds.length} 条任务记录。`)
      }
      if (failed.length) {
        const blocked = failed.filter((item) => item.reason.includes('不能') || item.reason.includes('不可') || item.reason.includes('冲突') || item.reason.includes('409'))
        const rest = failed.filter((item) => !blocked.includes(item))
        const detail = [
          blocked.length ? `${blocked.length} 条任务当前不可删` : '',
          rest.length ? `${rest.length} 条任务删除失败` : '',
        ].filter(Boolean).join('，') || failed[0]?.reason || '批量删除失败'
        ElMessage.error(detail)
      }
      clearSelectedEntries()
      selectionMode.value = false
      await load()
    } finally {
      bulkDeletingJobs.value = false
    }
  }

  function stopFallbackPolling() {
    if (pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
  }

  function startFallbackPolling() {
    if (pollTimer) return
    pollTimer = setInterval(() => {
      if (!loading.value && !bulkDeletingJobs.value && !jobActionBusy.value) {
        load().catch((e) => {
          err.value = e?.message ?? String(e)
        })
      }
    }, JOB_CENTER_FALLBACK_POLL_INTERVAL)
  }

  async function deleteSelectedProject() {
    if (selectedProjectId.value <= 0 || deletingProject.value) return
    try {
      await ElMessageBox.confirm(`确定彻底删除项目 #${selectedProjectId.value}？\n\n这会同时删除项目内容、执行记录和项目输出目录。\n该操作无法恢复。`, '删除项目确认', { type: 'warning' })
    } catch {
      return
    }
    deletingProject.value = true
    try {
      await api.deleteProject(selectedProjectId.value)
      ElMessage.success(`已删除项目 #${selectedProjectId.value}。`)
      router.push({ path: '/recent' })
    } catch (e: any) {
      if (isProjectMissingError(e)) {
        ElMessage.info(`项目 #${selectedProjectId.value} 已不存在，已返回项目列表。`)
        router.push({ path: '/recent' })
        return
      }
      ElMessage.error(e?.message ?? String(e))
    } finally {
      deletingProject.value = false
    }
  }

  onMounted(() => {
    unsubscribeFeedEvents = api.subscribeFeedEvents({
      onFeed: (payload) => {
        const projectIds = Array.isArray(payload?.project_ids) ? payload.project_ids.map((id: any) => Number(id)).filter((id: number) => Number.isFinite(id) && id > 0) : []
        if (!projectIds.length) return
        if (selectedProjectId.value <= 0 || projectIds.includes(selectedProjectId.value)) {
          load().catch((e) => {
            err.value = e?.message ?? String(e)
          })
        }
      },
      onOpen: () => {
        stopFallbackPolling()
        runtimeWarning.value = ''
      },
      onError: () => {
        runtimeWarning.value = '任务中心实时连接已中断，系统正在自动重连；当前会临时降级为轮询刷新。'
      },
      onStateChange: (state) => {
        feedConnectionState.value = state
        if (state === 'open') {
          stopFallbackPolling()
          runtimeWarning.value = ''
          return
        }
        if (state === 'polling') {
          startFallbackPolling()
          runtimeWarning.value = '任务中心实时连接暂未恢复，当前已降级为轮询刷新。'
        }
      },
    })
    load().catch((e) => {
      err.value = e?.message ?? String(e)
    })
  })

  onUnmounted(() => {
    stopFallbackPolling()
    unsubscribeFeedEvents?.()
    unsubscribeFeedEvents = null
  })

  return {
    jobs,
    loading,
    err,
    filterStatus,
    taskScope,
    deletingProject,
    projectionRebuilding,
    runtimeWarning,
    feedConnectionState,
    selectionMode,
    selectedEntryKeys,
    bulkDeletingJobs,
    selectedProjectId,
    jobActionBusy,
    statusOptions,
    taskScopeOptions,
    statusOptionMap,
    taskScopeOptionMap,
    visibleJobs,
    visibleJobMap,
    visibleEntries,
    deletableVisibleEntries,
    selectedDeletableEntries,
    allDeletableVisibleSelected,
    stats,
    normalizeStatus,
    load,
    projectLabel,
    diagnosticsConfig,
    isChainExpanded,
    toggleChain,
    openProject,
    openFinal,
    hasFinalOutput,
    statusTagType,
    canDeleteEntry,
    isSelectedEntry,
    setSelectionMode,
    toggleEntrySelection,
    selectAllVisibleEntries,
    clearSelectedEntries,
    pauseJob,
    resumeJob,
    cancelJob,
    retryJob,
    deleteJob,
    deleteSelectedJobs,
    deleteSelectedProject,
  }
}
let unsubscribeFeedEvents: null | (() => void) = null
