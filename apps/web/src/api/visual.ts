import { http } from './http'
import type { Asset, Job, Scene, SceneBindAssetIn } from './types'

export const visualApi = {
  patchScene: (sceneId: number, patch: Partial<Pick<Scene, 'narration' | 'media_query' | 'image_prompt' | 'image_negative' | 'duration_sec' | 'meta'>>) =>
    http<Scene>(`/api/scenes/${sceneId}`, { method: 'PATCH', body: JSON.stringify(patch) }),
  bindSceneAsset: (sceneId: number, body: SceneBindAssetIn) => http<Scene>(`/api/scenes/${sceneId}/bind-asset`, { method: 'POST', body: JSON.stringify(body) }),
  startImages: (projectId: number) => http<{ job: Job }>(`/api/projects/${projectId}/images`, { method: 'POST' }),
  startAutofillMedia: (projectId: number, prefer: 'video' | 'image' = 'video') =>
    http<{ job: Job }>(`/api/projects/${projectId}/autofill-media?prefer=${encodeURIComponent(prefer)}`, { method: 'POST' }),
  startSceneImage: (sceneId: number) => http<{ job: Job }>(`/api/scenes/${sceneId}/generate-image`, { method: 'POST' }),
  listSceneImageAssets: (sceneId: number, limit = 100) => http<Asset[]>(`/api/scenes/${sceneId}/image-assets?limit=${encodeURIComponent(String(limit))}`),
  useSceneImage: (sceneId: number, assetId: number) => http<Scene>(`/api/scenes/${sceneId}/use-image/${assetId}`, { method: 'POST' }),
}
