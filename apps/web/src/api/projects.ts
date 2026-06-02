import { http, uploadForm } from './http'
import { DEFAULT_CHANNEL_PACKS } from './types'
import { baselineApi } from './baseline'
import { pipelineApi } from './pipeline'
import { visualApi } from './visual'
import type {
  Asset,
  ChannelPack,
  JobCenterFeed,
  Job,
  Project,
  ProjectCenterFeed,
  ProjectDetail,
  ProjectQuality,
  ProjectRuntime,
  ProjectSummary,
} from './types'

export type FeedConnectionState = 'connecting' | 'open' | 'reconnecting' | 'polling' | 'closed'

type FeedSubscribeHandlers = {
  onFeed?: (payload: any) => void
  onOpen?: () => void
  onError?: () => void
  onStateChange?: (state: FeedConnectionState) => void
}

export const projectsApi = {
  listChannelPacks: async () => {
    try {
      const rows = await http<ChannelPack[]>('/api/channel-packs')
      return Array.isArray(rows) && rows.length ? rows : [...DEFAULT_CHANNEL_PACKS]
    } catch {
      return [...DEFAULT_CHANNEL_PACKS]
    }
  },
  listProjects: (workflow: 'mix' | '' = '') => http<Project[]>(`/api/projects${workflow ? `?workflow=${encodeURIComponent(workflow)}` : ''}`),
  getProjectCenterFeed: (limit = 200) => http<ProjectCenterFeed>(`/api/project-center/feed?limit=${encodeURIComponent(String(limit))}`),
  getProjectCenterFeedPage: (options: { limit?: number, cursor?: string } = {}) => {
    const params = new URLSearchParams()
    params.set('limit', String(options.limit ?? 200))
    if (options.cursor) params.set('cursor', options.cursor)
    return http<ProjectCenterFeed>(`/api/project-center/feed?${params.toString()}`)
  },
  getJobCenterFeed: (options: { limit?: number, scope?: 'project' | 'all', status?: 'all' | 'active' | 'failed' | 'done' | 'cancelled', projectId?: number } = {}) => {
    const params = new URLSearchParams()
    params.set('limit', String(options.limit ?? 200))
    params.set('scope', String(options.scope ?? 'project'))
    params.set('status', String(options.status ?? 'all'))
    if ((options.projectId ?? 0) > 0) params.set('project_id', String(options.projectId))
    return http<JobCenterFeed>(`/api/job-center/feed?${params.toString()}`)
  },
  getJobCenterFeedPage: (options: { limit?: number, scope?: 'project' | 'all', status?: 'all' | 'active' | 'failed' | 'done' | 'cancelled', projectId?: number, cursor?: string } = {}) => {
    const params = new URLSearchParams()
    params.set('limit', String(options.limit ?? 200))
    params.set('scope', String(options.scope ?? 'project'))
    params.set('status', String(options.status ?? 'all'))
    if ((options.projectId ?? 0) > 0) params.set('project_id', String(options.projectId))
    if (options.cursor) params.set('cursor', options.cursor)
    return http<JobCenterFeed>(`/api/job-center/feed?${params.toString()}`)
  },
  subscribeFeedEvents: (handlers: FeedSubscribeHandlers) => {
    let source: EventSource | null = null
    let retryTimer: ReturnType<typeof setTimeout> | null = null
    let stopped = false
    let attempts = 0

    const notifyState = (state: FeedConnectionState) => handlers.onStateChange?.(state)

    const cleanupSource = () => {
      if (!source) return
      try {
        source.close()
      } catch {
        // Ignore EventSource close failures.
      }
      source = null
    }

    const scheduleReconnect = () => {
      if (stopped) return
      attempts += 1
      const delayMs = Math.min(15000, 1000 * Math.max(1, attempts))
      notifyState(attempts >= 3 ? 'polling' : 'reconnecting')
      retryTimer = setTimeout(() => {
        retryTimer = null
        connect()
      }, delayMs)
    }

    const connect = () => {
      if (stopped) return
      cleanupSource()
      notifyState(attempts > 0 ? 'reconnecting' : 'connecting')
      source = new EventSource('/api/feed/events', { withCredentials: true })
      source.addEventListener('feed', (event) => {
        try {
          const payload = JSON.parse((event as MessageEvent).data || '{}')
          handlers.onFeed?.(payload)
        } catch {
          handlers.onFeed?.({})
        }
      })
      source.addEventListener('open', () => {
        attempts = 0
        notifyState('open')
        handlers.onOpen?.()
      })
      source.addEventListener('error', () => {
        handlers.onError?.()
        cleanupSource()
        scheduleReconnect()
      })
    }

    connect()
    return () => {
      stopped = true
      if (retryTimer) {
        clearTimeout(retryTimer)
        retryTimer = null
      }
      cleanupSource()
      notifyState('closed')
    }
  },
  createProject: (body: { title: string; channel_key: string; source_text?: string; render_config?: Record<string, any> }) =>
    http<Project>('/api/projects', { method: 'POST', body: JSON.stringify(body) }),
  getProject: (id: number) => http<ProjectDetail>(`/api/projects/${id}`),
  deleteProject: (id: number) => http<{ ok: boolean }>(`/api/projects/${id}`, { method: 'DELETE' }),
  ...baselineApi,
  getProjectSummary: (id: number) => http<ProjectSummary>(`/api/projects/${id}/summary`),
  getProjectRuntime: (id: number) => http<ProjectRuntime>(`/api/projects/${id}/runtime`),
  getProjectQuality: (id: number) => http<ProjectQuality>(`/api/projects/${id}/quality`),
  patchProject: (
    projectId: number,
    patch: Partial<Pick<Project, 'title' | 'script' | 'source_text' | 'character_profile' | 'publish_title' | 'publish_hashtags' | 'render_config' | 'voice_asset_id' | 'subtitle_asset_id'>>
  ) => http<Project>(`/api/projects/${projectId}`, { method: 'PATCH', body: JSON.stringify(patch) }),
  ...visualApi,
  ...pipelineApi,
  startRender: (projectId: number) => http<{ job: Job }>(`/api/projects/${projectId}/render`, { method: 'POST' }),
  listProjectAssets: (projectId: number, limit = 200) => http<Asset[]>(`/api/projects/${projectId}/assets?limit=${encodeURIComponent(String(limit))}`),
  uploadProjectAsset: async (projectId: number, file: File, kind: 'image' | 'audio' | 'video' | 'other' = 'audio', tag = 'project_source') => {
    const fd = new FormData()
    fd.append('file', file)
    fd.append('kind', kind)
    fd.append('tag', tag)
    return uploadForm<Asset>(`/api/projects/${projectId}/assets`, fd)
  },
  finalExport: (projectId: number) => http<{ exists: boolean; url: string; size: number }>(`/api/projects/${projectId}/exports/final`),
}
