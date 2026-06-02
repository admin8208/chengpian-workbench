import type { ComputedRef, Ref } from 'vue'
import { api, type Scene } from '../../../api'

export function useMixProjectSceneActions(options: {
  selectedScene: ComputedRef<Scene | null>
  selectedSceneId: Ref<number | null>
  busy: Ref<boolean>
  err: Ref<string>
  info: Ref<string>
  patchSceneLocal: (scene: Scene) => void
  refreshSummaryOnly: () => Promise<void>
  refreshAssetsOnly: () => Promise<void>
  loadSceneHistory: (sceneId: number) => Promise<void>
  focusSceneIssuesBase: (notify: (message: string) => void) => void
}) {
  const { selectedScene, selectedSceneId, busy, err, info, patchSceneLocal, refreshSummaryOnly, refreshAssetsOnly, loadSceneHistory, focusSceneIssuesBase } = options

  async function patchScene(patch: Partial<Pick<Scene, 'narration' | 'media_query' | 'image_prompt' | 'duration_sec'>>) {
    const scene = selectedScene.value
    if (!scene) return
    busy.value = true
    err.value = ''
    try {
      const nextScene = await api.patchScene(scene.id, patch)
      patchSceneLocal(nextScene)
      await refreshSummaryOnly()
    } catch (e: any) {
      err.value = e?.message ?? String(e)
    } finally {
      busy.value = false
    }
  }

  function focusSceneIssues() {
    focusSceneIssuesBase((message) => {
      info.value = message
    })
  }

  async function useSceneHistoryAsset(assetId: number) {
    const scene = selectedScene.value
    if (!scene) return
    busy.value = true
    err.value = ''
    try {
      const nextScene = await api.useSceneImage(scene.id, assetId)
      patchSceneLocal(nextScene)
      await Promise.all([refreshSummaryOnly(), refreshAssetsOnly(), selectedSceneId.value === scene.id ? loadSceneHistory(scene.id) : Promise.resolve()])
      info.value = `已切换镜头 ${scene.idx} 的素材。`
    } catch (e: any) {
      err.value = e?.message ?? String(e)
    } finally {
      busy.value = false
    }
  }

  return {
    patchScene,
    focusSceneIssues,
    useSceneHistoryAsset,
  }
}
