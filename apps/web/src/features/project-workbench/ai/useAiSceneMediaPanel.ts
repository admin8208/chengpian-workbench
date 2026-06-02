import { computed, onUnmounted, ref, watch, type ComputedRef, type Ref } from 'vue'
import type { Asset, Scene } from '../../../api'
import type { ScenePreview } from '../../../components/project/scenePreview'

export function useAiSceneMediaPanel(options: {
  selectedSceneId: Ref<number | null>
  selectedScene: ComputedRef<Scene | null>
  assetById: ComputedRef<Map<number, Asset>>
}) {
  const { selectedSceneId, selectedScene, assetById } = options
  const sceneHistoryAssets = ref<Asset[]>([])
  const sceneHistoryBusy = ref(false)
  const sceneHistoryErr = ref('')
  const suggestBusy = ref(false)
  const suggestErr = ref('')
  const suggestItems = ref<any[]>([])
  const suggestProvider = ref('wikimedia')
  const suggestKind = ref<'video' | 'image'>('image')
  const suggestKindOptions = computed<Array<'video' | 'image'>>(() => ['image'])
  const currentSceneAsset = computed(() => {
    const scene = selectedScene.value
    if (!scene) return null
    const aid = Number(scene.image_asset_id || 0)
    if (!aid) return null
    return assetById.value.get(aid) || null
  })
  const inferMediaKind = (url: string) => (/([.]mp4|[.]webm|[.]mov)(\?|$)/i.test(String(url)) ? 'video' : 'image')
  const currentScenePreview = computed<ScenePreview | null>(() => {
    const asset = currentSceneAsset.value
    if (asset?.url) {
      return { kind: asset.kind === 'video' ? 'video' : 'image', url: asset.url, label: asset.kind === 'video' ? '视频素材' : '图片素材' }
    }
    const fallbackUrl = String(selectedScene.value?.image_url || '').trim()
    if (!fallbackUrl) return null
    const kind = inferMediaKind(fallbackUrl)
    return { kind, url: fallbackUrl, label: kind === 'video' ? '视频素材（兜底预览）' : '图片素材（兜底预览）' }
  })
  const suggestPreviewUrl = (item: any) => String(item?.thumb_url || item?.preview_url || item?.file_url || '').trim()
  const suggestPreviewKind = (item: any) => (String(item?.kind || '').trim().toLowerCase() === 'video' ? 'video' : inferMediaKind(suggestPreviewUrl(item)))
  const visibleSceneHistoryAssets = computed(() => {
    const currentId = Number(selectedScene.value?.image_asset_id || 0)
    return sceneHistoryAssets.value.filter((asset) => asset.id !== currentId)
  })

  async function loadSceneHistory() {
    sceneHistoryBusy.value = false
    sceneHistoryErr.value = ''
    sceneHistoryAssets.value = []
  }

  async function loadSuggestions() {
    suggestBusy.value = false
    suggestErr.value = ''
    suggestItems.value = []
  }

  onUnmounted(() => {
    sceneHistoryAssets.value = []
  })

  watch(() => selectedSceneId.value, () => {
    void loadSceneHistory()
    void loadSuggestions()
  })

  return {
    sceneHistoryAssets,
    sceneHistoryBusy,
    sceneHistoryErr,
    currentSceneAsset,
    currentScenePreview,
    suggestBusy,
    suggestErr,
    suggestItems,
    suggestProvider,
    suggestKind,
    suggestKindOptions,
    suggestPreviewUrl,
    suggestPreviewKind,
    loadSceneHistory,
    loadSuggestions,
    importAndBind: async () => {},
    visibleSceneHistoryAssets,
  }
}
