import { computed, ref, type Ref } from 'vue'
import { api, type ImageProvider, type ImageStatus } from '../../../../api'

const IMAGE_TEST_SIZE_OPTIONS = ['1024x1024', '944x1664', '1664x944'] as const
const PRODUCTION_IMAGE_TEST_PROMPT = '一个明亮现代的办公室会议场景，三到五人围桌讨论，镜头干净，主体明确，电影感光线，写实风格，构图稳定，适合视频分镜首帧'

export function useSettingsImage(options: {
  err: Ref<string>
  info: Ref<string>
}) {
  const { err, info } = options
  const imageStatus = ref<ImageStatus | null>(null)
  const imageProviders = ref<ImageProvider[]>([])
  const imageLoading = ref(true)

  const imageName = ref('')
  const imageBaseUrl = ref('')
  const imageModel = ref('')
  const imageKey = ref('')
  const imageSaving = ref(false)
  const imageTesting = ref(false)
  const imageTestResult = ref('')
  const imageTestSize = ref<(typeof IMAGE_TEST_SIZE_OPTIONS)[number]>('1664x944')
  const imageValidationPrompt = ref(PRODUCTION_IMAGE_TEST_PROMPT)

  const imageSetupState = computed<'loading' | 'ready' | 'missing'>(() => (imageLoading.value ? 'loading' : imageStatus.value?.has_default ? 'ready' : 'missing'))
  const imageQuickSummary = computed(() => {
    if (imageLoading.value) return '正在读取生图模型配置…'
    if (!imageStatus.value?.has_default) return '未设置默认生图模型'
    return `${imageStatus.value.default_provider_name || '已配置'} · ${imageStatus.value.default_model || '未设置模型'}`
  })

  function hydrateImageForm() {
    const currentImage = imageProviders.value.find((provider) => provider.is_default) || imageProviders.value.find((provider) => provider.id === imageStatus.value?.default_provider_id)
    if (currentImage) {
      imageName.value = currentImage.name
      imageBaseUrl.value = currentImage.base_url
      imageModel.value = currentImage.default_model
      imageKey.value = currentImage.api_key || ''
    } else {
      imageKey.value = ''
    }
  }

  async function loadImage(failures?: string[]) {
    imageLoading.value = true
    try {
      imageStatus.value = await api.imageStatus()
      imageProviders.value = await api.imageProviders()
    } catch (e: any) {
      imageStatus.value = null
      imageProviders.value = []
      failures?.push(`生图配置加载失败：${e?.message ?? String(e)}`)
    } finally {
      imageLoading.value = false
    }
  }

  async function saveImage(loadAll: () => Promise<void>) {
    imageSaving.value = true
    err.value = ''
    info.value = ''
    try {
      const currentImage = imageProviders.value.find((provider) => provider.is_default) || imageProviders.value.find((provider) => provider.id === imageStatus.value?.default_provider_id)
      const apiKey = imageKey.value.trim() || currentImage?.api_key || ''
      await api.imageCreateProvider({
        name: imageName.value.trim() || '默认生图模型',
        type: 'openai_compat',
        base_url: imageBaseUrl.value.trim(),
        default_model: imageModel.value.trim(),
        enabled: true,
        is_default: true,
        api_key: apiKey,
      })
      info.value = '生图模型设置已保存。'
      await loadAll()
    } catch (e: any) {
      err.value = e?.message ?? String(e)
    } finally {
      imageSaving.value = false
    }
  }

  async function testImage() {
    imageTesting.value = true
    imageTestResult.value = ''
    try {
      const fallback = imageProviders.value.find((p) => p.is_default) || imageProviders.value[0]
      const prompt = imageValidationPrompt.value.trim() || PRODUCTION_IMAGE_TEST_PROMPT
      const size = imageTestSize.value
      const res = await api.imageTest({
        provider_id: fallback?.id,
        base_url: imageBaseUrl.value.trim(),
        default_model: imageModel.value.trim(),
        api_key: imageKey.value.trim(),
        prompt,
        size,
      })
      imageTestResult.value = res.message || (res.ok ? '测试成功：生图模型可用。' : (res.error || '测试失败：生图模型不可用。'))
    } catch (e: any) {
      imageTestResult.value = e?.message ?? String(e)
    } finally {
      imageTesting.value = false
    }
  }

  return {
    imageStatus,
    imageProviders,
    imageLoading,
    imageName,
    imageBaseUrl,
    imageModel,
    imageKey,
    imageSaving,
    imageTesting,
    imageTestResult,
    imageTestSize,
    imageValidationPrompt,
    imageTestSizeOptions: IMAGE_TEST_SIZE_OPTIONS,
    imageSetupState,
    imageQuickSummary,
    hydrateImageForm,
    loadImage,
    saveImage,
    testImage,
  }
}
