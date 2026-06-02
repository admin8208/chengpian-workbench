import { http, uploadForm } from './http'
import type { Asset, MediaProvider, WebSearchResult } from './types'
import type { RenderAspect } from '../renderConfig'

export const assetsApi = {
  listLibraryAssets: (kind: 'image' | 'audio' | 'video' | 'other' = 'image', query = '', limit = 60) =>
    http<Asset[]>(`/api/library/assets?kind=${encodeURIComponent(kind)}&query=${encodeURIComponent(query)}&limit=${encodeURIComponent(String(limit))}`),
  uploadLibraryAsset: async (file: File, kind: 'image' | 'audio' | 'video' | 'other' = 'image', tag = 'library') => {
    const fd = new FormData()
    fd.append('file', file)
    fd.append('kind', kind)
    fd.append('tag', tag)
    return uploadForm<Asset>('/api/library/assets', fd)
  },
  deleteLibraryAsset: (assetId: number) => http<{ ok: boolean; deleted: number }>(`/api/library/assets/${assetId}`, { method: 'DELETE' }),
  clearLibraryAssets: (kind: 'image' | 'audio' | 'video' | 'other' = 'video') =>
    http<{ ok: boolean; deleted: number; skipped_active: number }>(`/api/library/assets?kind=${encodeURIComponent(kind)}`, { method: 'DELETE' }),
  webSearch: (provider: MediaProvider, kind: 'image' | 'video' | 'audio', query: string, limit = 24, aspect: RenderAspect = 'landscape') =>
    http<WebSearchResult>(
      `/api/library/web-search?provider=${encodeURIComponent(provider)}&kind=${encodeURIComponent(kind)}&query=${encodeURIComponent(query)}&limit=${encodeURIComponent(String(limit))}&aspect=${encodeURIComponent(aspect)}`
    ),
  importFromWeb: (body: {
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
    width?: number | null
    height?: number | null
    duration_sec?: number | null
  }) => http<Asset>('/api/library/import', { method: 'POST', body: JSON.stringify(body) }),
  importProjectFromWeb: (projectId: number, body: {
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
    width?: number | null
    height?: number | null
    duration_sec?: number | null
  }) => http<Asset>(`/api/projects/${projectId}/import-web`, { method: 'POST', body: JSON.stringify(body) }),
}
