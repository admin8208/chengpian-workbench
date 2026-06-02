import { http, uploadForm } from './http'

export type VideoToAudioResult = {
  ok: boolean
  filename: string
  mime: string
  size: number
  url: string
  rel_path: string
}

export type VideoToAudioProjectResult = {
  ok: boolean
  project_id: number
}

export const toolsApi = {
  videoToAudio: async (file: File, outputFormat: 'mp3' = 'mp3') => {
    const fd = new FormData()
    fd.append('file', file)
    fd.append('output_format', outputFormat)
    return uploadForm<VideoToAudioResult>('/api/tools/video-to-audio', fd, 600000)
  },
  videoUrlToAudio: async (url: string) => {
    return http<VideoToAudioResult>('/api/tools/video-url-to-audio', { method: 'POST', body: JSON.stringify({ url }) })
  },
  createAudioProjectFromTool: (body: { title: string; channel_key: string; material_mode: 'network' | 'ai'; rel_path: string }) =>
    http<VideoToAudioProjectResult>('/api/tools/video-to-audio/project', { method: 'POST', body: JSON.stringify(body) }),
}
