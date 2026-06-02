import { assetsApi } from './assets'
import { baselineApi } from './baseline'
import { authApi } from './auth'
import { jobsApi } from './jobs'
import { pipelineApi } from './pipeline'
import { projectsApi } from './projects'
import { settingsApi } from './settings'
import { systemApi } from './system'
import { toolsApi } from './tools'
import { ttsApi } from './tts'
import { cloudApi } from './cloud'
import { visualApi } from './visual'
export { clearCachedAuthStatus, fetchAuthStatus, readCachedAuthStatus, writeCachedAuthStatus } from './authState'

export * from './types'
export type { FeedConnectionState } from './projects'
export type { VideoToAudioResult } from './tools'
export type { VideoToAudioProjectResult } from './tools'

export const api = {
  ...authApi,
  ...baselineApi,
  ...pipelineApi,
  ...projectsApi,
  ...jobsApi,
  ...assetsApi,
  ...settingsApi,
  ...ttsApi,
  ...systemApi,
  ...toolsApi,
  ...cloudApi,
  ...visualApi,
}
