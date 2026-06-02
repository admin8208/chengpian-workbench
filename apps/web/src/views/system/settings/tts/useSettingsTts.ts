import { computed, ref, type Ref } from 'vue'
import { api, type EdgeVoiceInfo, type OfflineVoiceInfo, type TtsStatus } from '../../../../api'

const VOICE_RATE_OPTIONS = ['-20%', '-10%', '+0%', '+10%', '+20%', '+30%', '+40%'] as const

export function useSettingsTts(options: {
  err: Ref<string>
  info: Ref<string>
  busy: Ref<boolean>
}) {
  const { err, info, busy } = options
  const tts = ref<TtsStatus | null>(null)
  const ttsLoading = ref(true)
  const ttsBackend = ref('offline_piper')
  const offlineVoiceId = ref('zh_CN-huayan-medium')
  const edgeVoiceId = ref('zh-CN-XiaoxiaoNeural')
  const defaultVoiceRate = ref<string>('+0%')
  const showAllEdgeVoices = ref(false)
  const ttsInstallRunning = ref(false)
  const cleanupInfo = ref('')
  const ttsPreviewText = ref('你现在听到的是配音试听，这段声音会尽量接近最终成片的口播感觉。')
  const ttsPreviewRate = ref<string>('+0%')
  const ttsPreviewBusy = ref(false)
  const ttsPreviewUrl = ref('')
  const ttsPreviewMode = ref<'offline_piper' | 'edge'>('offline_piper')

  const offlineVoiceCatalog: Record<string, { label: string; note: string }> = {
    'zh_CN-huayan-medium': { label: '华岩', note: '默认中文音色，最稳' },
    'zh_CN-huayan-x_low': { label: '华岩（轻量）', note: '体积更小，质量更低' },
    'zh_CN-chaowen-medium': { label: '超文', note: '偏平稳，适合讲述' },
    'zh_CN-xiao_ya-medium': { label: '小雅', note: '偏柔和，适合情绪内容' },
  }

  const edgeVoiceCatalog: Record<string, { label: string; note: string }> = {
    'zh-CN-XiaoxiaoNeural': { label: '晓晓', note: '微软在线 · 普通话女声' },
    'zh-CN-XiaoyiNeural': { label: '晓伊', note: '微软在线 · 普通话女声' },
    'zh-CN-YunxiNeural': { label: '云希', note: '微软在线 · 普通话男声' },
    'zh-CN-YunyangNeural': { label: '云扬', note: '微软在线 · 普通话男声' },
  }

  const ttsSetupState = computed<'loading' | 'ready' | 'missing'>(() => {
    if (ttsLoading.value) return 'loading'
    const backend = String(tts.value?.backend || 'offline_piper')
    const offlineReady = Boolean(tts.value?.offline_installed)
    const edgeReady = Boolean(tts.value?.edge_synthesis_ok) || Number(tts.value?.available_edge_zh_cn_voice_count || 0) > 0
    if (backend === 'offline_piper') return offlineReady ? 'ready' : 'missing'
    if (backend === 'edge') return edgeReady ? 'ready' : 'missing'
    return offlineReady || edgeReady ? 'ready' : 'missing'
  })
  const ttsQuickSummary = computed(() => {
    if (ttsLoading.value) return '正在读取配音状态…'
    const rate = String(tts.value?.default_voice_rate || '+0%')
    return `后端：${tts.value?.backend || '未设置'} · 默认语速 ${rate === '+0%' ? '正常' : rate} · 在线 ${tts.value?.available_edge_zh_cn_voice_count || 0}/${tts.value?.available_edge_voice_count || 0} · 本机 ${tts.value?.offline_installed_voice_count || 0}/${tts.value?.available_offline_voice_count || 0}`
  })
  const ttsBackendLabel = computed(() => {
    if (ttsBackend.value === 'auto') return '自动选择（优先在线，失败回退本机）'
    if (ttsBackend.value === 'edge') return '在线配音（音色更自然）'
    return '本机配音（稳定，无需联网）'
  })

  const availableOfflineVoices = computed<OfflineVoiceInfo[]>(() => tts.value?.available_offline_voices || [])
  const availableEdgeVoices = computed<EdgeVoiceInfo[]>(() => tts.value?.available_edge_voices || [])
  const zhCnEdgeVoices = computed(() => availableEdgeVoices.value.filter((voice) => String(voice.locale || '') === 'zh-CN'))
  const visibleEdgeVoices = computed(() => (showAllEdgeVoices.value ? availableEdgeVoices.value : zhCnEdgeVoices.value))
  const compatibleOfflineVoices = computed(() => availableOfflineVoices.value.filter((voice) => voice.compatible))
  const installedOfflineVoices = computed(() => availableOfflineVoices.value.filter((voice) => voice.installed))
  const incompatibleOfflineVoices = computed(() => availableOfflineVoices.value.filter((voice) => !voice.compatible))

  const offlineVoiceOptions = computed(() => {
    const ids = new Set<string>()
    const installed = tts.value?.offline_installed_voice_ids || []
    for (const voice of availableOfflineVoices.value) ids.add(String(voice.voice_id || ''))
    for (const id of installed) ids.add(String(id))
    ids.add(String(offlineVoiceId.value || 'zh_CN-huayan-medium'))
    for (const id of Object.keys(offlineVoiceCatalog)) ids.add(id)
    return [...ids].map((id) => ({
      value: id,
      label: availableOfflineVoices.value.find((voice) => voice.voice_id === id)?.label || offlineVoiceCatalog[id]?.label || id,
      note: availableOfflineVoices.value.find((voice) => voice.voice_id === id)?.reason || offlineVoiceCatalog[id]?.note || '本机离线音色',
      installed: installed.includes(id),
    }))
  })

  function edgeVoiceFriendlyMeta(id: string, voice?: EdgeVoiceInfo) {
    const preset = edgeVoiceCatalog[id]
    if (preset) return preset
    const rawLabel = String(voice?.label || id).trim()
    const locale = String(voice?.locale || '').trim()
    const gender = String(voice?.gender || '').trim()
    const shortName = rawLabel
      .replace(/^Microsoft\s+/i, '')
      .replace(/\s+Online.*$/i, '')
      .replace(/\s*\(Natural\)/i, '')
      .trim() || id
    const localeLabel = locale === 'zh-CN' ? '普通话' : (locale || '在线')
    const genderLabel = gender === 'Female' ? '女声' : gender === 'Male' ? '男声' : ''
    return {
      label: shortName,
      note: ['微软在线', localeLabel, genderLabel].filter(Boolean).join(' · '),
    }
  }

  const edgeVoiceOptions = computed(() => {
    const ids = new Set<string>()
    for (const voice of visibleEdgeVoices.value) ids.add(String(voice.voice_id || ''))
    if (edgeVoiceId.value.trim()) ids.add(edgeVoiceId.value.trim())
    return [...ids].map((id) => {
      const voice = availableEdgeVoices.value.find((item) => item.voice_id === id)
      const meta = edgeVoiceFriendlyMeta(id, voice)
      return {
        value: id,
        label: meta.label,
        note: meta.note,
      }
    })
  })

  const previewVoiceName = computed(() => edgeVoiceId.value.trim() || 'zh-CN-XiaoxiaoNeural')
  const previewModeLabel = computed(() => (ttsPreviewMode.value === 'edge' ? '在线配音试听' : '本机配音试听'))

  function hydrateTtsForm() {
    ttsBackend.value = String(tts.value?.backend || 'offline_piper')
    offlineVoiceId.value = String(tts.value?.offline_voice_id || 'zh_CN-huayan-medium')
    edgeVoiceId.value = String(tts.value?.edge_voice_id || 'zh-CN-XiaoxiaoNeural')
    defaultVoiceRate.value = String(tts.value?.default_voice_rate || '+0%')
    ttsPreviewRate.value = defaultVoiceRate.value
  }

  async function loadTts(failures?: string[]) {
    ttsLoading.value = true
    try {
      tts.value = await api.ttsStatus()
    } catch (e: any) {
      tts.value = null
      failures?.push(`配音配置加载失败：${e?.message ?? String(e)}`)
    } finally {
      ttsLoading.value = false
    }
  }

  async function saveTtsBackend() {
    busy.value = true
    err.value = ''
    info.value = ''
    try {
      tts.value = await api.ttsSetBackend(ttsBackend.value, offlineVoiceId.value.trim() || null, edgeVoiceId.value.trim() || null, defaultVoiceRate.value)
      info.value = '配音后端已保存。'
    } catch (e: any) {
      err.value = e?.message ?? String(e)
    } finally {
      busy.value = false
    }
  }

  async function reloadTtsStatus() {
    ttsLoading.value = true
    try {
      tts.value = await api.ttsStatus(true)
      info.value = '已刷新配音状态。'
    } catch (e: any) {
      err.value = e?.message ?? String(e)
    } finally {
      ttsLoading.value = false
    }
  }

  async function previewCurrentTts(mode?: 'offline_piper' | 'edge') {
    if (!ttsPreviewText.value.trim()) return
    if (mode) ttsPreviewMode.value = mode
    ttsPreviewBusy.value = true
    ttsPreviewUrl.value = ''
    err.value = ''
    try {
      const res = await api.ttsPreview(
        ttsPreviewText.value.trim(),
        previewVoiceName.value,
        defaultVoiceRate.value,
        1.0,
        ttsPreviewMode.value,
        ttsPreviewMode.value === 'offline_piper' ? offlineVoiceId.value.trim() || null : null,
      )
      if (!res.ok || !res.url) throw new Error(res.error || '试听生成失败')
      ttsPreviewUrl.value = res.url
    } catch (e: any) {
      err.value = e?.message ?? String(e)
    } finally {
      ttsPreviewBusy.value = false
    }
  }

  async function installOfflineTts() {
    ttsInstallRunning.value = true
    err.value = ''
    try {
      await api.ttsOfflineInstallAllCompatible()
      info.value = '已开始安装全部兼容中文音色。系统会自动跳过不兼容或下载失败的音色。'
    } catch (e: any) {
      err.value = e?.message ?? String(e)
    } finally {
      ttsInstallRunning.value = false
    }
  }

  async function cleanupIncompatibleVoices() {
    busy.value = true
    cleanupInfo.value = ''
    try {
      const res = await api.ttsOfflineCleanupIncompatible()
      cleanupInfo.value = res.deleted_voice_ids?.length ? `已清理：${res.deleted_voice_ids.join('、')}` : '没有发现需要清理的不兼容音色。'
    } catch (e: any) {
      err.value = e?.message ?? String(e)
    } finally {
      busy.value = false
    }
  }

  return {
    tts,
    ttsLoading,
    ttsBackend,
    offlineVoiceId,
    edgeVoiceId,
    defaultVoiceRate,
    showAllEdgeVoices,
    ttsInstallRunning,
    cleanupInfo,
    ttsPreviewText,
    ttsPreviewRate,
    ttsPreviewBusy,
    ttsPreviewUrl,
    ttsPreviewMode,
    voiceRateOptions: VOICE_RATE_OPTIONS,
    ttsSetupState,
    ttsQuickSummary,
    ttsBackendLabel,
    availableOfflineVoices,
    availableEdgeVoices,
    visibleEdgeVoices,
    compatibleOfflineVoices,
    installedOfflineVoices,
    incompatibleOfflineVoices,
    offlineVoiceOptions,
    edgeVoiceOptions,
    previewModeLabel,
    hydrateTtsForm,
    loadTts,
    saveTtsBackend,
    reloadTtsStatus,
    previewCurrentTts,
    installOfflineTts,
    cleanupIncompatibleVoices,
  }
}
