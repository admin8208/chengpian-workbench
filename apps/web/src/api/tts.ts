import { http } from './http'
import type { Job, TtsPreview, TtsStatus } from './types'

export const ttsApi = {
  ttsPreview: (text: string, voice: string, rate = '+0%', volume = 1.0, backend?: 'offline_piper' | 'edge' | 'auto', offline_voice_id?: string | null) =>
    http<TtsPreview>('/api/tts/preview', { method: 'POST', body: JSON.stringify({ text, voice, rate, volume, backend, offline_voice_id: offline_voice_id ?? null }) }),
  ttsStatus: (probe = false) => http<TtsStatus>(`/api/tts/status${probe ? '?probe=1' : ''}`),
  ttsSetBackend: (backend: string, offline_voice_id?: string | null, edge_voice_id?: string | null, default_voice_rate?: string | null) =>
    http<TtsStatus>('/api/tts/backend', { method: 'POST', body: JSON.stringify({ backend, offline_voice_id: offline_voice_id ?? null, edge_voice_id: edge_voice_id ?? null, default_voice_rate: default_voice_rate ?? null }) }),
  ttsOfflineInstall: (offline_voice_id?: string | null) =>
    http<{ job: Job }>('/api/tts/offline/install', { method: 'POST', body: JSON.stringify({ backend: 'offline_piper', offline_voice_id: offline_voice_id ?? null }) }),
  ttsOfflineInstallAllCompatible: () => http<{ job: Job }>('/api/tts/offline/install-all-compatible', { method: 'POST' }),
  ttsOfflineCleanupIncompatible: () => http<{ ok: boolean; deleted_voice_ids?: string[]; freed_bytes?: number }>('/api/tts/offline/cleanup-incompatible', { method: 'POST' }),
}
