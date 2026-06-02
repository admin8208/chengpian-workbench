<script setup lang="ts">
import AssetPreview from './AssetPreview.vue'
import type { ScenePreview } from './scenePreview'
import type { Asset, Scene } from '../../api'

type SceneTag = {
  key: string
  label: string
  tone: string
}

type NetworkSceneDetailModel = {
  selectedScene: Scene | null
  selectedSceneTags: SceneTag[]
  busy: boolean
  currentScenePreview: ScenePreview | null
  currentSceneAsset: Asset | null
  suggestBusy: boolean
  suggestErr: string
  suggestItems: any[]
  suggestProvider: string
  suggestKind: string
  suggestKindOptions: Array<'video' | 'image'>
  sceneHistoryBusy: boolean
  sceneHistoryErr: string
  visibleSceneHistoryAssets: Asset[]
  suggestPreviewUrl: (item: any) => string
  suggestPreviewKind: (item: any) => string
  sceneAssetType: (scene: Scene | null | undefined) => string
  patchSceneNarration: (value: string) => Promise<void>
  patchSceneMediaQuery: (value: string) => Promise<void>
  patchSceneDuration: (value: number) => Promise<void>
  loadSuggestions: () => Promise<void>
  importAndBind: (item: any) => Promise<void>
  useHistoryAsset: (assetId: number) => Promise<void>
  downloadAsset: (asset: Asset) => void
}

defineProps<{ model: NetworkSceneDetailModel }>()
</script>

<template>
  <section class="detail-panel">
    <div class="cardTitle">当前镜头</div>
    <div v-if="!model.selectedScene" class="muted empty-text">选择一个镜头。</div>
    <div v-else class="detail-stack">
      <div class="row detail-head">
        <div>
          <div class="scene-title">镜头 {{ model.selectedScene.idx }}</div>
          <div class="muted scene-title-sub">{{ model.sceneAssetType(model.selectedScene) }} · {{ model.selectedScene.duration_sec }}s</div>
        </div>
        <div class="row">
          <div v-for="tag in model.selectedSceneTags" :key="tag.key" class="pill" :class="tag.tone">{{ tag.label }}</div>
        </div>
      </div>

      <div class="softItem">
        <div class="muted label-strong">当前素材预览</div>
        <div v-if="!model.selectedScene.image_asset_id" class="muted top-gap">还没有绑定素材。</div>
        <div v-else-if="!model.currentScenePreview" class="muted top-gap">已记录素材，但预览资源还没加载出来。可先继续换素材或稍后再看。</div>
        <div v-else class="top-gap">
          <video v-if="model.currentScenePreview.kind === 'video'" class="scenePreview" :src="model.currentScenePreview.url" controls playsinline />
          <img v-else-if="model.currentScenePreview.kind === 'image'" class="scenePreview" :src="model.currentScenePreview.url" alt="当前镜头素材" />
          <a v-else class="btnGhost" :href="model.currentScenePreview.url" target="_blank">打开当前素材</a>
          <div class="muted top-gap">{{ model.currentScenePreview.label }} · {{ model.currentSceneAsset?.tag || '已绑定' }}</div>
        </div>
      </div>

      <label class="muted label-strong">旁白</label>
      <textarea class="ta" :value="model.selectedScene.narration" @change="model.patchSceneNarration(($event.target as HTMLTextAreaElement).value)" />

      <label class="muted label-strong">素材检索关键词（media_query）</label>
      <input
        class="input"
        :value="model.selectedScene.media_query || ''"
        placeholder="例如：夜晚城市天际线 / 办公室加班 / 河流日出"
        @change="model.patchSceneMediaQuery(($event.target as HTMLInputElement).value)"
      />

      <div>
        <label class="muted label-strong">时长（秒）</label>
        <input
          class="input"
          type="number"
          step="0.5"
          min="2"
          :value="model.selectedScene.duration_sec"
          @change="model.patchSceneDuration(Number(($event.target as HTMLInputElement).value))"
        />
      </div>

      <div class="row search-head">
        <div>
          <div class="muted label-strong">可选素材（快速纠偏）</div>
          <div class="muted small-top-gap">可以直接导入并绑定到当前镜头。</div>
        </div>
        <div class="row">
          <select class="select" :value="model.suggestProvider" :disabled="model.suggestBusy" @change="model.suggestProvider = ($event.target as HTMLSelectElement).value">
            <option value="wikimedia">Wikimedia (无需API Key)</option>
            <option value="pexels">Pexels</option>
            <option value="pixabay">Pixabay</option>
          </select>
          <select class="select" :value="model.suggestKind" :disabled="model.suggestBusy" @change="model.suggestKind = ($event.target as HTMLSelectElement).value">
            <option v-for="kind in model.suggestKindOptions" :key="kind" :value="kind">{{ kind === 'video' ? '视频' : '图片' }}</option>
          </select>
          <button class="btnGhost" :disabled="model.suggestBusy" @click="model.loadSuggestions">搜索</button>
        </div>
      </div>
      <div v-if="model.suggestErr" class="muted suggest-error">{{ model.suggestErr }}</div>
      <div v-if="model.suggestItems.length" class="suggestGrid">
        <div v-for="item in model.suggestItems" :key="item.file_url" class="item suggestItem">
          <div v-if="model.suggestPreviewUrl(item)" class="suggestMedia">
            <video v-if="model.suggestPreviewKind(item) === 'video'" :src="model.suggestPreviewUrl(item)" class="suggestPreview" controls playsinline preload="metadata" />
            <img v-else-if="model.suggestPreviewKind(item) === 'image'" :src="model.suggestPreviewUrl(item)" class="suggestPreview" alt="候选素材预览" />
          </div>
          <div class="muted suggestTitle">{{ item.provider }} · {{ item.kind }}</div>
          <div class="muted suggestSub">{{ item.title }}</div>
          <div class="muted suggest-meta">
            <span v-if="item.width && item.height">{{ item.width }}×{{ item.height }}</span>
            <span v-if="item.duration_sec"> · {{ Math.round(item.duration_sec) }}s</span>
          </div>
          <div class="row suggest-actions">
            <a class="btnGhost" :href="item.page_url" target="_blank">来源页</a>
            <button class="btn" :disabled="model.busy" @click="model.importAndBind(item)">导入并绑定</button>
          </div>
        </div>
      </div>

      <div class="softItem">
        <div v-if="model.sceneHistoryBusy" class="muted">正在加载…</div>
        <div v-if="model.sceneHistoryErr" class="muted history-error">{{ model.sceneHistoryErr }}</div>
        <div v-else-if="model.visibleSceneHistoryAssets.length" class="sceneHistoryGrid history-grid-top-gap">
          <AssetPreview
            v-for="asset in model.visibleSceneHistoryAssets"
            :key="asset.id"
            :asset="asset"
            :selected="false"
            @select-asset="model.useHistoryAsset(asset.id)"
            @download-asset="model.downloadAsset(asset)"
          />
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.detail-panel {
  min-width: 0;
}

.empty-text {
  margin-top: 10px;
}

.detail-stack {
  margin-top: 10px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.detail-head {
  justify-content: space-between;
  align-items: start;
  gap: 12px;
}

.scene-title {
  font-weight: 820;
}

.scene-title-sub {
  margin-top: 4px;
}

.label-strong {
  font-weight: 760;
}

.top-gap {
  margin-top: 8px;
}

.small-top-gap {
  margin-top: 4px;
}

.search-head {
  justify-content: space-between;
  align-items: end;
}

.suggest-error,
.history-error {
  white-space: pre-wrap;
}

.suggestMedia {
  margin-bottom: 8px;
  border-radius: 10px;
  overflow: hidden;
  background: rgba(15, 23, 42, 0.04);
}

.suggestPreview,
.scenePreview {
  width: 100%;
  max-width: 100%;
  display: block;
  object-fit: cover;
}

.scenePreview {
  border-radius: 8px;
  height: auto;
}

.suggestPreview {
  aspect-ratio: 16 / 9;
  background: rgba(15, 23, 42, 0.04);
}

.suggest-meta {
  margin-top: 4px;
}

.suggest-actions {
  margin-top: 8px;
  justify-content: space-between;
}

.history-grid-top-gap {
  margin-top: 10px;
}
</style>
