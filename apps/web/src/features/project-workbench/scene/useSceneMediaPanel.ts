import { computed, onUnmounted, ref, watch, type ComputedRef, type Ref } from 'vue'
import { api, type Asset, type MediaProvider, type MediaProviderStatus, type Scene } from '../../../api'
import type { ScenePreview } from '../../../components/project/scenePreview'
import type { RenderAspect } from '../../../renderConfig'

type ImportWebItem = {
  provider: MediaProvider
  kind: 'image' | 'video' | 'audio'
  title: string
  page_url: string
  file_url: string
  thumb_url?: string | null
  preview_url?: string | null
  license_short?: string
  license_url?: string | null
  author?: string
  attribution?: string
}

export function useSceneMediaPanel(options: {
  projectId: Ref<number | null>
  selectedSceneId: Ref<number | null>
  selectedScene: ComputedRef<Scene | null>
  materialMode: ComputedRef<'ai' | 'network'>
  projectAspect: ComputedRef<RenderAspect>
  mediaProviderStatus: Ref<MediaProviderStatus[]>
  assetById: ComputedRef<Map<number, Asset>>
  refreshAssetsOnly: () => Promise<void>
  refreshSummaryOnly: () => Promise<void>
  patchSceneLocal: (scene: Scene) => void
  setBusy: (next: boolean) => void
  setErr: (message: string) => void
  setInfo: (message: string) => void
}) {
  const {
    projectId,
    selectedSceneId,
    selectedScene,
    materialMode,
    projectAspect,
    mediaProviderStatus,
    assetById,
    refreshAssetsOnly,
    refreshSummaryOnly,
    patchSceneLocal,
    setBusy,
    setErr,
    setInfo,
  } = options

  const sceneHistoryAssets = ref<Asset[]>([])
  const sceneHistoryBusy = ref(false)
  const sceneHistoryErr = ref('')

  const suggestBusy = ref(false)
  const suggestErr = ref('')
  const suggestItems = ref<any[]>([])
  const suggestProvider = ref<MediaProvider>('wikimedia')
  const suggestKind = ref<'video' | 'image'>('video')

  let sceneHistorySeq = 0
  let suggestSeq = 0
  let sceneSuggestTimer: number | null = null

  function inferMediaKind(url: string) {
    const lower = String(url || '').trim().toLowerCase()
    if (!lower) return 'unknown'
    if (/(\.mp4|\.webm|\.mov|\.mkv)(\?|$)/.test(lower)) return 'video'
    if (/(\.png|\.jpg|\.jpeg|\.webp|\.gif)(\?|$)/.test(lower)) return 'image'
    return 'unknown'
  }

  const currentSceneAsset = computed(() => {
    const scene = selectedScene.value
    if (!scene) return null
    const aid = Number(scene.image_asset_id || 0)
    if (!aid) return null
    const fromProject = assetById.value.get(aid)
    if (fromProject) return fromProject
    return sceneHistoryAssets.value.find((a) => a.id === aid) || null
  })

  const currentScenePreview = computed<ScenePreview | null>(() => {
    const asset = currentSceneAsset.value
    if (asset?.url) {
      return {
        kind: asset.kind === 'video' || asset.kind === 'image' ? asset.kind : inferMediaKind(asset.url),
        url: asset.url,
        label: asset.kind === 'video' ? '视频素材' : asset.kind === 'image' ? '图片素材' : '已绑定素材',
      }
    }
    const fallbackUrl = String(selectedScene.value?.image_url || '').trim()
    if (!fallbackUrl) return null
    const kind = inferMediaKind(fallbackUrl)
    return {
      kind,
      url: fallbackUrl,
      label: kind === 'video' ? '视频素材（兜底预览）' : kind === 'image' ? '图片素材（兜底预览）' : '已绑定素材（兜底预览）',
    }
  })

  function suggestPreviewUrl(item: any) {
    return String(item?.thumb_url || item?.preview_url || item?.file_url || '').trim()
  }

  function suggestPreviewKind(item: any) {
    const kind = String(item?.kind || '').trim().toLowerCase()
    if (kind === 'video' || kind === 'image') return kind
    return inferMediaKind(suggestPreviewUrl(item))
  }

  function providerSupportedKinds(provider: MediaProvider): Array<'video' | 'image'> {
    const row = mediaProviderStatus.value.find((p) => p.provider === provider)
    const kinds = Array.isArray(row?.supported_kinds) && row.supported_kinds.length ? row.supported_kinds : ['image', 'video']
    const out = kinds.filter((k) => k === 'video' || k === 'image') as Array<'video' | 'image'>
    return out.length ? out : ['video', 'image']
  }

  const suggestKindOptions = computed<Array<'video' | 'image'>>(() => providerSupportedKinds(suggestProvider.value))

  watch(
    () => `${suggestProvider.value}:${suggestKindOptions.value.join(',')}`,
    () => {
      if (!suggestKindOptions.value.includes(suggestKind.value)) {
        suggestKind.value = suggestKindOptions.value[0] || 'video'
      }
    },
    { immediate: true }
  )

  async function loadSceneHistory(sceneIdArg?: number | null) {
    const sceneId = Number(sceneIdArg || selectedSceneId.value || 0)
    if (!sceneId) {
      sceneHistoryAssets.value = []
      sceneHistoryErr.value = ''
      return
    }
    const seq = ++sceneHistorySeq
    sceneHistoryBusy.value = true
    sceneHistoryErr.value = ''
    try {
      const next = await api.listSceneImageAssets(sceneId, 24)
      if (seq !== sceneHistorySeq || selectedSceneId.value !== sceneId) return
      sceneHistoryAssets.value = next
    } catch (e: any) {
      if (seq !== sceneHistorySeq || selectedSceneId.value !== sceneId) return
      sceneHistoryErr.value = e?.message ?? String(e)
      sceneHistoryAssets.value = []
    } finally {
      if (seq === sceneHistorySeq) sceneHistoryBusy.value = false
    }
  }

  async function loadSuggestions(sceneArg?: Scene | null) {
    if (materialMode.value === 'ai') {
      suggestItems.value = []
      suggestErr.value = ''
      return
    }
    const scene = sceneArg || selectedScene.value
    if (!scene) {
      suggestItems.value = []
      suggestErr.value = ''
      return
    }
    const seq = ++suggestSeq
    const sceneId = scene.id
    suggestBusy.value = true
    suggestErr.value = ''
    suggestItems.value = []
    if (!suggestKindOptions.value.includes(suggestKind.value)) {
      suggestErr.value = `${suggestProvider.value} 不支持 ${suggestKind.value} 搜索`
      suggestBusy.value = false
      return
    }
    try {
      const q = (scene.media_query || scene.narration || '').trim()
      const res = await api.webSearch(suggestProvider.value, suggestKind.value, q, 12, projectAspect.value)
      if (seq !== suggestSeq || selectedSceneId.value !== sceneId) return
      suggestItems.value = (res as any).items || []
      if (!suggestItems.value.length) {
        suggestErr.value = ''
      }
    } catch (e: any) {
      if (seq !== suggestSeq || selectedSceneId.value !== sceneId) return
      suggestErr.value = e?.message ?? String(e)
    } finally {
      if (seq === suggestSeq) suggestBusy.value = false
    }
  }

  async function importAndBind(it: ImportWebItem) {
    const scene = selectedScene.value
    if (!scene) return
    setBusy(true)
    setErr('')
    try {
      const pid = projectId.value
      if (!pid) throw new Error('项目不存在')
      const asset = await api.importProjectFromWeb(pid, {
        provider: it.provider,
        kind: it.kind,
        title: it.title,
        page_url: it.page_url,
        file_url: it.file_url,
        thumb_url: it.thumb_url,
        preview_url: it.preview_url,
        license_short: it.license_short,
        license_url: it.license_url,
        author: it.author,
        attribution: it.attribution,
      })
      const nextScene = await api.bindSceneAsset(scene.id, { asset_id: asset.id })
      patchSceneLocal(nextScene)
      await Promise.all([
        refreshSummaryOnly(),
        refreshAssetsOnly(),
        selectedSceneId.value === scene.id ? loadSceneHistory(scene.id) : Promise.resolve(),
      ])
      setInfo(`已导入并绑定到镜头 ${scene.idx}。`)
    } catch (e: any) {
      setErr(e?.message ?? String(e))
    } finally {
      setBusy(false)
    }
  }

  const visibleSceneHistoryAssets = computed(() => {
    const currentId = Number(selectedScene.value?.image_asset_id || 0)
    return sceneHistoryAssets.value.filter((asset) => asset.id !== currentId)
  })

  watch(
    () => selectedSceneId.value,
    async () => {
      if (sceneSuggestTimer) window.clearTimeout(sceneSuggestTimer)
      suggestSeq += 1
      suggestBusy.value = false
      suggestErr.value = ''
      suggestItems.value = []
      sceneHistoryErr.value = ''
      await loadSceneHistory()
      await refreshAssetsOnly()
      if (materialMode.value === 'ai') return
      const scene = selectedScene.value
      if (!scene) return
      if (!scene.image_asset_id) {
        sceneSuggestTimer = window.setTimeout(() => {
          loadSuggestions(scene).catch(() => {})
        }, 120)
      }
    }
  )

  onUnmounted(() => {
    sceneHistorySeq += 1
    suggestSeq += 1
    if (sceneSuggestTimer) window.clearTimeout(sceneSuggestTimer)
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
    importAndBind,
    visibleSceneHistoryAssets,
  }
}
