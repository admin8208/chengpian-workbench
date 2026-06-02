import { computed, ref, type Ref } from 'vue'
import { api, type LlmProvider, type LlmStatus } from '../../../../api'

export function useSettingsLlm(options: {
  err: Ref<string>
  info: Ref<string>
}) {
  const { err, info } = options
  const llmStatus = ref<LlmStatus | null>(null)
  const llmProviders = ref<LlmProvider[]>([])
  const llmLoading = ref(true)

  const llmName = ref('')
  const llmType = ref<'openai_compat' | 'ollama'>('openai_compat')
  const llmBaseUrl = ref('')
  const llmModel = ref('')
  const llmKey = ref('')
  const llmSaving = ref(false)
  const llmTesting = ref(false)
  const llmTestResult = ref('')

  const llmSetupState = computed<'loading' | 'ready' | 'missing'>(() => (llmLoading.value ? 'loading' : llmStatus.value?.has_default ? 'ready' : 'missing'))
  const llmQuickSummary = computed(() => {
    if (llmLoading.value) return '正在读取大模型配置…'
    if (!llmStatus.value?.has_default) return '未设置默认大模型'
    return `${llmStatus.value.default_provider_name || '已配置'} · ${llmStatus.value.default_model || '未设置模型'}`
  })

  function hydrateLlmForm() {
    const currentLlm = llmProviders.value.find((provider) => provider.is_default) || llmProviders.value.find((provider) => provider.id === llmStatus.value?.default_provider_id)
    if (currentLlm) {
      llmName.value = currentLlm.name
      llmType.value = currentLlm.type === 'ollama' ? 'ollama' : 'openai_compat'
      llmBaseUrl.value = currentLlm.base_url
      llmModel.value = currentLlm.default_model
      llmKey.value = currentLlm.api_key || ''
    } else {
      llmKey.value = ''
    }
  }

  async function loadLlm(failures?: string[]) {
    llmLoading.value = true
    try {
      llmStatus.value = await api.llmStatus()
      llmProviders.value = await api.llmProviders()
    } catch (e: any) {
      llmStatus.value = null
      llmProviders.value = []
      failures?.push(`大模型配置加载失败：${e?.message ?? String(e)}`)
    } finally {
      llmLoading.value = false
    }
  }

  async function saveLlm(loadAll: () => Promise<void>) {
    llmSaving.value = true
    err.value = ''
    info.value = ''
    try {
      const currentLlm = llmProviders.value.find((provider) => provider.is_default) || llmProviders.value.find((provider) => provider.id === llmStatus.value?.default_provider_id)
      const apiKey = llmKey.value.trim() || currentLlm?.api_key || ''
      await api.llmCreateProvider({
        name: llmName.value.trim() || '默认大模型',
        type: llmType.value,
        base_url: llmBaseUrl.value.trim(),
        default_model: llmModel.value.trim(),
        enabled: true,
        is_default: true,
        api_key: llmType.value === 'openai_compat' ? apiKey : '',
      })
      info.value = '大模型设置已保存。'
      await loadAll()
    } catch (e: any) {
      err.value = e?.message ?? String(e)
    } finally {
      llmSaving.value = false
    }
  }

  async function testLlm() {
    llmTesting.value = true
    llmTestResult.value = ''
    try {
      const fallback = llmProviders.value.find((p) => p.is_default) || llmProviders.value[0]
      const res = await api.llmTest({
        provider_id: fallback?.id,
        type: llmType.value,
        base_url: llmBaseUrl.value.trim(),
        default_model: llmModel.value.trim(),
        api_key: llmType.value === 'openai_compat' ? llmKey.value.trim() : '',
        prompt: '请只返回 JSON：{"ok": true}',
      })
      llmTestResult.value = res.message || (res.ok ? '测试成功：大模型可用。' : (res.error || '测试失败：大模型不可用。'))
    } catch (e: any) {
      llmTestResult.value = e?.message ?? String(e)
    } finally {
      llmTesting.value = false
    }
  }

  return {
    llmStatus,
    llmProviders,
    llmLoading,
    llmName,
    llmType,
    llmBaseUrl,
    llmModel,
    llmKey,
    llmSaving,
    llmTesting,
    llmTestResult,
    llmSetupState,
    llmQuickSummary,
    hydrateLlmForm,
    loadLlm,
    saveLlm,
    testLlm,
  }
}
