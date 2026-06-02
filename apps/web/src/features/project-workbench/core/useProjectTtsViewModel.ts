import { computed, ref, type ComputedRef, type Ref } from 'vue'
import type { EdgeVoiceInfo, OfflineVoiceInfo, ProjectDetail, TtsStatus } from '../../../api'

const OFFLINE_VOICE_CATALOG: Record<string, string> = {
  'zh_CN-huayan-medium': '华岩',
  'zh_CN-huayan-x_low': '华岩（轻量）',
  'zh_CN-chaowen-medium': '超文',
  'zh_CN-xiao_ya-medium': '小雅',
}

const EDGE_VOICE_CATALOG: Record<string, string> = {
  'zh-CN-XiaoxiaoNeural': '晓晓',
  'zh-CN-XiaoyiNeural': '晓伊',
  'zh-CN-YunxiNeural': '云希',
  'zh-CN-YunyangNeural': '云扬',
}

export function normalizeVoiceRate(raw: unknown) {
  const text = String(raw || '').trim()
  const match = text.match(/^([+-]?)(\d+)%$/)
  if (!match) return '+0%'
  const sign = match[1] === '-' ? -1 : 1
  const value = Math.max(-20, Math.min(40, Number(match[2]) * sign))
  return `${value >= 0 ? '+' : ''}${value}%`
}

function offlineVoiceLabel(id: string, voices?: OfflineVoiceInfo[] | null) {
  const voiceId = String(id || '').trim()
  if (!voiceId) return '未设置'
  return voices?.find((voice) => voice.voice_id === voiceId)?.label || OFFLINE_VOICE_CATALOG[voiceId] || voiceId
}

function edgeVoiceLabel(id: string, voices?: EdgeVoiceInfo[] | null) {
  const voiceId = String(id || '').trim()
  if (!voiceId) return '未设置'
  const matched = voices?.find((voice) => voice.voice_id === voiceId)
  if (matched?.label) return matched.label
  return EDGE_VOICE_CATALOG[voiceId] || voiceId
}

export function useProjectTtsViewModel(options: {
  projectId: ComputedRef<number | null>
  project: Ref<ProjectDetail | null>
  err: Ref<string>
  info: Ref<string>
}) {
  const { projectId: _projectId, project: _project, err: _err, info: _info } = options

  const ttsStatus = ref<TtsStatus | null>(null)
  const projectVoiceRate = computed(() => normalizeVoiceRate(ttsStatus.value?.default_voice_rate))
  const projectVoiceRateLabel = computed(() => (projectVoiceRate.value === '+0%' ? '正常语速' : projectVoiceRate.value))

  const currentTtsBackendLabel = computed(() => {
    const backend = String(ttsStatus.value?.backend || 'offline_piper').trim().toLowerCase()
    if (backend === 'auto') return '自动选择（优先在线，失败回退本机）'
    if (backend === 'edge') return '在线配音'
    return '本机配音'
  })

  const currentTtsVoiceLabel = computed(() => {
    const backend = String(ttsStatus.value?.backend || 'offline_piper').trim().toLowerCase()
    if (backend === 'edge') return edgeVoiceLabel(String(ttsStatus.value?.edge_voice_id || ''), ttsStatus.value?.available_edge_voices)
    if (backend === 'auto') {
      const edgeName = edgeVoiceLabel(String(ttsStatus.value?.edge_voice_id || ''), ttsStatus.value?.available_edge_voices)
      const offlineName = offlineVoiceLabel(String(ttsStatus.value?.offline_voice_id || ''), ttsStatus.value?.available_offline_voices)
      return `${edgeName} / ${offlineName}`
    }
    return offlineVoiceLabel(String(ttsStatus.value?.offline_voice_id || ''), ttsStatus.value?.available_offline_voices)
  })

  function setTtsStatus(next: TtsStatus | null) {
    ttsStatus.value = next
  }

  return {
    ttsStatus,
    setTtsStatus,
    projectVoiceRate,
    projectVoiceRateLabel,
    currentTtsBackendLabel,
    currentTtsVoiceLabel,
  }
}
