import { ref, type ComputedRef, type Ref } from 'vue'
import { api, type Asset, type MediaProviderStatus, type ProjectDetail, type ProjectQuality, type ProjectRuntime, type ProjectSummary, type TtsStatus } from '../../../api'

export function useMixProjectLoader(options: {
  projectId: ComputedRef<number | null>
  project: Ref<ProjectDetail | null>
  projectAssets: Ref<Asset[]>
  runtime: Ref<ProjectRuntime | null>
  summary: Ref<ProjectSummary | null>
  quality: Ref<ProjectQuality | null>
  qualityNotice: Ref<string>
  mediaProviderStatus: Ref<MediaProviderStatus[]>
  loadState: Ref<'loading' | 'ready' | 'error' | 'not_found'>
  loadMessage: Ref<string>
  err: Ref<string>
  hydrateProjectInputs: () => void
  ensureSelectedScene: (project: ProjectDetail | null | undefined) => void
  resetProjectState: () => void
  setLoadFailure: (message: string) => void
  setFinalStatus: (status: any) => void
  setTtsStatus: (status: TtsStatus | null) => void
  loadProjectJobs: (limit?: number) => Promise<void>
  applyAutoSelectedVideo: () => void
  refreshQualityOnly: () => Promise<void>
  onLoaded: () => void
}) {
  const {
    projectId,
    project,
    projectAssets,
    runtime,
    summary,
    quality,
    qualityNotice,
    mediaProviderStatus,
    loadState,
    loadMessage,
    err,
    hydrateProjectInputs,
    ensureSelectedScene,
    resetProjectState,
    setLoadFailure,
    setFinalStatus,
    setTtsStatus,
    loadProjectJobs,
    applyAutoSelectedVideo,
    refreshQualityOnly,
    onLoaded,
  } = options

  const loadSeq = ref(0)

  async function load() {
    const seq = ++loadSeq.value
    const id = projectId.value
    err.value = ''
    resetProjectState()
    loadState.value = 'loading'
    loadMessage.value = '正在加载项目…'
    if (!id) {
      setLoadFailure('项目链接无效或项目不存在。')
      return
    }

    let initialProject: ProjectDetail
    try {
      initialProject = await api.getProject(id)
    } catch (e: any) {
      if (seq !== loadSeq.value) return
      setLoadFailure(e?.message ?? String(e))
      return
    }

    if (seq !== loadSeq.value) return
    project.value = initialProject
    hydrateProjectInputs()
    ensureSelectedScene(project.value)
    loadState.value = 'ready'
    quality.value = null
    qualityNotice.value = ''

    const [assetsRes, finRes, runtimeRes, summaryRes, mediaStatusRes, ttsStatusRes] = await Promise.allSettled([
      api.listProjectAssets(id, 400),
      api.finalExport(id),
      api.getProjectRuntime(id),
      api.getProjectSummary(id),
      api.mediaProviders(),
      api.ttsStatus(),
    ])

    if (seq !== loadSeq.value) return
    if (assetsRes.status === 'fulfilled') projectAssets.value = assetsRes.value
    if (finRes.status === 'fulfilled') setFinalStatus(finRes.value)
    runtime.value = runtimeRes.status === 'fulfilled' ? runtimeRes.value : null
    if (summaryRes.status === 'fulfilled') summary.value = summaryRes.value
    if (mediaStatusRes.status === 'fulfilled') mediaProviderStatus.value = mediaStatusRes.value
    if (ttsStatusRes.status === 'fulfilled') setTtsStatus(ttsStatusRes.value)

    const secondaryErrors = [assetsRes, finRes, runtimeRes, summaryRes, mediaStatusRes, ttsStatusRes]
      .filter((res): res is PromiseRejectedResult => res.status === 'rejected')
      .map((res) => String(res.reason?.message || res.reason || '').trim())
      .filter(Boolean)
    if (secondaryErrors.length) err.value = `部分项目数据加载失败：${secondaryErrors[0]}`

    try {
      await loadProjectJobs(200)
      if (seq !== loadSeq.value) return
    } catch (e: any) {
      if (seq !== loadSeq.value) return
      if (!err.value) err.value = `任务状态加载失败：${e?.message ?? String(e)}`
    }

    applyAutoSelectedVideo()
    onLoaded()
    void refreshQualityOnly()
  }

  function retryLoad() {
    load().catch((e) => setLoadFailure(e?.message ?? String(e)))
  }

  function invalidateLoad() {
    loadSeq.value += 1
  }

  return {
    load,
    retryLoad,
    invalidateLoad,
  }
}
