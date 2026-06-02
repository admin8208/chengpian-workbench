import type { ComputedRef, Ref } from 'vue'
import type { Asset, MediaProviderStatus, ProjectDetail, Scene } from '../../../api'
import type { RenderAspect } from '../../../renderConfig'
import { useSceneMediaPanel } from './useSceneMediaPanel'
import { useProjectSceneIssues } from './useProjectSceneIssues'
import { useMixProjectSceneActions } from './useMixProjectSceneActions'

type FlowStep = 'input' | 'storyboard' | 'voice' | 'media' | 'render'

export function useProjectSceneWorkspace(options: {
  projectId: Ref<number | null>
  project: Ref<ProjectDetail | null>
  selectedSceneId: Ref<number | null>
  selectedScene: ComputedRef<Scene | null>
  materialMode: ComputedRef<'ai' | 'network'>
  projectAspect: ComputedRef<RenderAspect>
  mediaProviderStatus: Ref<MediaProviderStatus[]>
  assetById: ComputedRef<Map<number, Asset>>
  patchSceneLocal: (scene: Scene) => void
  refreshAssetsOnly: () => Promise<void>
  refreshSummaryOnly: () => Promise<void>
  busy: Ref<boolean>
  err: Ref<string>
  info: Ref<string>
  goStep: (step: FlowStep, manual?: boolean) => void
}) {
  const media = useSceneMediaPanel({
    projectId: options.projectId,
    selectedSceneId: options.selectedSceneId,
    selectedScene: options.selectedScene,
    materialMode: options.materialMode,
    projectAspect: options.projectAspect,
    mediaProviderStatus: options.mediaProviderStatus,
    assetById: options.assetById,
    refreshAssetsOnly: options.refreshAssetsOnly,
    refreshSummaryOnly: options.refreshSummaryOnly,
    patchSceneLocal: options.patchSceneLocal,
    setBusy: (next) => {
      options.busy.value = next
    },
    setErr: (message) => {
      options.err.value = message
    },
    setInfo: (message) => {
      options.info.value = message
    },
  })

  const issues = useProjectSceneIssues({
    project: options.project,
    selectedSceneId: options.selectedSceneId,
    selectedScene: options.selectedScene,
    assetById: options.assetById,
    materialMode: options.materialMode,
    loadSuggestions: media.loadSuggestions,
    goStep: options.goStep,
  })

  const actions = useMixProjectSceneActions({
    selectedScene: options.selectedScene,
    selectedSceneId: options.selectedSceneId,
    busy: options.busy,
    err: options.err,
    info: options.info,
    patchSceneLocal: options.patchSceneLocal,
    refreshSummaryOnly: options.refreshSummaryOnly,
    refreshAssetsOnly: options.refreshAssetsOnly,
    loadSceneHistory: media.loadSceneHistory,
    focusSceneIssuesBase: issues.focusSceneIssues,
  })

  return {
    ...media,
    ...issues,
    ...actions,
  }
}
