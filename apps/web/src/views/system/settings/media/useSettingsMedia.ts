import { computed, ref, type Ref } from 'vue'
import { api, type MediaProvider, type MediaProviderStatus, type WebMediaItem } from '../../../../api'
import type { RenderAspect } from '../../../../renderConfig'

export function useSettingsMedia(options: {
  err: Ref<string>
  info: Ref<string>
}) {
  const { err, info } = options
  const mediaProviders = ref<MediaProviderStatus[]>([])
  const mediaLoading = ref(true)
  const pexelsKey = ref('')
  const pixabayKey = ref('')
  const mediaSaving = ref(false)
  const mediaTestQuery = ref('办公室 团队合作 会议室')
  const mediaTestKind = ref<'video' | 'image'>('video')
  const mediaTestAspect = ref<RenderAspect>('landscape')
  const mediaTestProvider = ref<MediaProvider>('wikimedia')
  const mediaTestItems = ref<WebMediaItem[]>([])
  const mediaTestResult = ref('')
  const mediaTesting = ref(false)

  const mediaSetupState = computed<'loading' | 'ready' | 'missing'>(() => {
    if (mediaLoading.value) return 'loading'
    return mediaProviders.value.some((provider) => provider.ok || provider.has_api_key) ? 'ready' : 'missing'
  })

  const mediaQuickSummary = computed(() => {
    const wikimedia = mediaProviders.value.find((provider) => provider.provider === 'wikimedia')
    const pexels = mediaProviders.value.find((provider) => provider.provider === 'pexels')
    const pixabay = mediaProviders.value.find((provider) => provider.provider === 'pixabay')
    return `Wikimedia：${wikimedia?.ok ? '可用' : '未就绪'} · Pexels：${pexels?.has_api_key ? '已配 Key' : '未配 Key'} · Pixabay：${pixabay?.has_api_key ? '已配 Key' : '未配 Key'}`
  })

  function hydrateMediaForm() {
    pexelsKey.value = mediaProviders.value.find((provider) => provider.provider === 'pexels')?.api_key || ''
    pixabayKey.value = mediaProviders.value.find((provider) => provider.provider === 'pixabay')?.api_key || ''
  }

  async function loadMedia(failures?: string[]) {
    mediaLoading.value = true
    try {
      mediaProviders.value = await api.mediaProviders()
    } catch (e: any) {
      mediaProviders.value = []
      failures?.push(`素材源配置加载失败：${e?.message ?? String(e)}`)
    } finally {
      mediaLoading.value = false
    }
  }

  async function saveMediaKey(provider: 'pexels' | 'pixabay', key: string, loadAll: () => Promise<void>) {
    if (!key.trim()) return
    mediaSaving.value = true
    err.value = ''
    info.value = ''
    try {
      await api.mediaSetKey(provider, key.trim())
      info.value = `${provider === 'pexels' ? 'Pexels' : 'Pixabay'} 接口密钥已保存。`
      await loadAll()
    } catch (e: any) {
      err.value = e?.message ?? String(e)
    } finally {
      mediaSaving.value = false
    }
  }

  async function runMediaTest() {
    mediaTesting.value = true
    mediaTestResult.value = ''
    mediaTestItems.value = []
    try {
      const res = await api.mediaTest(mediaTestProvider.value, mediaTestKind.value, mediaTestQuery.value.trim(), 4, mediaTestAspect.value)
      mediaTestItems.value = res.items || []
      mediaTestResult.value = res.ok ? '测试成功' : (res.error || '测试失败')
    } catch (e: any) {
      mediaTestResult.value = e?.message ?? String(e)
    } finally {
      mediaTesting.value = false
    }
  }

  return {
    mediaProviders,
    mediaLoading,
    pexelsKey,
    pixabayKey,
    mediaSaving,
    mediaTestQuery,
    mediaTestKind,
    mediaTestAspect,
    mediaTestProvider,
    mediaTestItems,
    mediaTestResult,
    mediaTesting,
    mediaSetupState,
    mediaQuickSummary,
    hydrateMediaForm,
    loadMedia,
    saveMediaKey,
    runMediaTest,
  }
}
