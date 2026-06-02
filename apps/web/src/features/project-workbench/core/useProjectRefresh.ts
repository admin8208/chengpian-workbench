import type { Ref } from 'vue'
import { api, type Asset, type ProjectDetail, type ProjectQuality, type ProjectRuntime, type ProjectSummary } from '../../../api'

type UseProjectRefreshArgs = {
  projectId: Ref<number | null>
  project: Ref<ProjectDetail | null>
  runtime: Ref<ProjectRuntime | null>
  summary: Ref<ProjectSummary | null>
  quality: Ref<ProjectQuality | null>
  qualityLoading: Ref<boolean>
  qualityNotice: Ref<string>
  projectAssets: Ref<Asset[]>
  selectedVideoUrl: Ref<string>
  userSelectedVideo: Ref<boolean>
  finalStatus: Ref<{ exists?: boolean; url?: string } | null>
  exportVideos: Ref<Array<{ url: string }>>
  ensureSelectedScene: (project: ProjectDetail | null) => void
  preserveSelectionAfterAssetsRefresh: () => void
  onRefreshError?: (message: string) => void
}

export function useProjectRefresh(args: UseProjectRefreshArgs) {
  function getProjectId() {
    return args.projectId.value
  }

  async function refreshAssetsOnly() {
    const id = getProjectId()
    if (!id) return
    try {
      args.projectAssets.value = await api.listProjectAssets(id, 400)
      args.preserveSelectionAfterAssetsRefresh()
    } catch (e: any) {
      args.onRefreshError?.(e?.message ?? '项目素材刷新失败')
    }
  }

  async function refreshSummaryOnly() {
    const id = getProjectId()
    if (!id) return
    try {
      const [p, r, s, fin] = await Promise.all([
        api.getProject(id),
        api.getProjectRuntime(id),
        api.getProjectSummary(id),
        api.finalExport(id),
      ])
      args.project.value = p
      args.ensureSelectedScene(p)
      args.runtime.value = r
      args.summary.value = s
      args.finalStatus.value = fin
      if (!args.userSelectedVideo.value) args.preserveSelectionAfterAssetsRefresh()
    } catch (e: any) {
      args.onRefreshError?.(e?.message ?? '项目状态刷新失败')
    }
  }

  async function refreshQualityOnly() {
    const id = getProjectId()
    if (!id) return
    args.qualityLoading.value = true
    args.qualityNotice.value = ''
    try {
      args.quality.value = await api.getProjectQuality(id)
    } catch (e: any) {
      args.quality.value = null
      const msg = String(e?.message ?? String(e || '')).trim()
      args.qualityNotice.value = msg ? `质量分析稍后补充：${msg}` : '质量分析稍后补充。'
    } finally {
      args.qualityLoading.value = false
    }
  }

  return {
    refreshAssetsOnly,
    refreshSummaryOnly,
    refreshQualityOnly,
  }
}
