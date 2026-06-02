import { http } from './http'
import type { RenderAspect } from '../renderConfig'
import type {
  ImageProvider,
  ImageStatus,
  LlmProvider,
  LlmStatus,
  MediaProvider,
  MediaProviderStatus,
  WebMediaItem,
} from './types'

export const settingsApi = {
  mediaProviders: () => http<MediaProviderStatus[]>('/api/media/providers'),
  mediaSetKey: (provider: MediaProvider, api_key: string) =>
    http<{ ok: boolean }>(`/api/media/providers/${encodeURIComponent(provider)}/key`, { method: 'POST', body: JSON.stringify({ api_key }) }),
  mediaTest: (provider: MediaProvider, kind: 'image' | 'video' | 'audio', query: string, limit = 5, aspect: RenderAspect = 'landscape') =>
    http<{ ok: boolean; items?: WebMediaItem[]; error?: string }>(`/api/media/providers/${encodeURIComponent(provider)}/test`, {
      method: 'POST',
      body: JSON.stringify({ kind, query, limit, aspect }),
    }),
  llmStatus: () => http<LlmStatus>('/api/llm/status'),
  llmProviders: () => http<LlmProvider[]>('/api/llm/providers'),
  llmCreateProvider: (p: Omit<LlmProvider, 'id'> & { api_key?: string }) => http<LlmProvider>('/api/llm/providers', { method: 'POST', body: JSON.stringify(p) }),
  llmSetKey: (id: number, api_key: string) => http<{ ok: boolean }>(`/api/llm/providers/${id}/key`, { method: 'POST', body: JSON.stringify({ api_key }) }),
  llmTest: (body: { provider_id?: number; type?: string; base_url?: string; default_model?: string; api_key?: string; prompt: string }) =>
    http<{ ok: boolean; data?: any; error?: string; message?: string }>('/api/llm/test', { method: 'POST', body: JSON.stringify(body), timeoutMs: 600000 }),
  imageStatus: () => http<ImageStatus>('/api/image/status'),
  imageProviders: () => http<ImageProvider[]>('/api/image/providers'),
  imageCreateProvider: (p: Omit<ImageProvider, 'id'> & { api_key?: string }) => http<ImageProvider>('/api/image/providers', { method: 'POST', body: JSON.stringify(p) }),
  imageSetKey: (id: number, api_key: string) => http<{ ok: boolean }>(`/api/image/providers/${id}/key`, { method: 'POST', body: JSON.stringify({ api_key }) }),
  imageTest: (body: { provider_id?: number; base_url?: string; default_model?: string; api_key?: string; prompt: string; size?: string }) =>
    http<{ ok: boolean; data?: any; error?: string; message?: string }>('/api/image/test', { method: 'POST', body: JSON.stringify(body), timeoutMs: 600000 }),
}
