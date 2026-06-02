import type { ComputedRef, Ref } from 'vue'
import type { Asset, MediaProviderStatus, ProjectDetail, Scene } from '../../../api'
import type { RenderAspect } from '../../../renderConfig'

import { useMixProjectSceneActions } from '../scene/useMixProjectSceneActions'
import { useProjectSceneIssues } from '../scene/useProjectSceneIssues'
import { useAiSceneMediaPanel } from './useAiSceneMediaPanel'

export function useAiProjectSceneWorkspace(options: {
  projectId: Ref<number>
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
  goStep: (step: 'storyboard', manual?: boolean) => void
}) {
  const media = useAiSceneMediaPanel({ selectedSceneId: options.selectedSceneId, selectedScene: options.selectedScene, assetById: options.assetById })
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
  return { ...media, ...issues, ...actions }
}
