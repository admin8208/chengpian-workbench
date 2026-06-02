<script setup lang="ts">
import type { ScenePreview } from './scenePreview'
import type { Asset, Scene } from '../../api'

type SceneTag = {
  key: string
  label: string
  tone: string
}

type AiSceneDetailModel = {
  selectedScene: Scene | null
  selectedSceneTags: SceneTag[]
  busy: boolean
  currentScenePreview: ScenePreview | null
  currentSceneAsset: Asset | null
  sceneAssetType: (scene: Scene | null | undefined) => string
  patchSceneNarration: (value: string) => Promise<void>
  patchSceneImagePrompt: (value: string) => Promise<void>
  patchSceneDuration: (value: number) => Promise<void>
  generateSceneImage: () => Promise<void>
}

defineProps<{ model: AiSceneDetailModel }>()
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
        <div class="muted label-strong">当前画面预览</div>
        <div v-if="!model.selectedScene.image_asset_id" class="muted top-gap">还没有生成镜头图。</div>
        <div v-else-if="!model.currentScenePreview" class="muted top-gap">已记录镜头图，但预览资源还没加载出来。可先继续重生成或稍后再看。</div>
        <div v-else class="top-gap">
          <video v-if="model.currentScenePreview.kind === 'video'" class="scenePreview" :src="model.currentScenePreview.url" controls playsinline />
          <img v-else-if="model.currentScenePreview.kind === 'image'" class="scenePreview" :src="model.currentScenePreview.url" alt="当前镜头图" />
          <a v-else class="btnGhost" :href="model.currentScenePreview.url" target="_blank">打开当前镜头图</a>
          <div class="muted top-gap">{{ model.currentScenePreview.label }} · {{ model.currentSceneAsset?.tag || '已绑定' }}</div>
        </div>
      </div>

      <label class="muted label-strong">旁白</label>
      <textarea class="ta" :value="model.selectedScene.narration" @change="model.patchSceneNarration(($event.target as HTMLTextAreaElement).value)" />

      <label class="muted label-strong">画面提示词（image_prompt）</label>
      <input
        class="input"
        :value="model.selectedScene.image_prompt || ''"
        placeholder="例如：夜晚城市天际线，电影感，逆光，横版构图"
        @change="model.patchSceneImagePrompt(($event.target as HTMLInputElement).value)"
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

      <div class="softItem muted short-copy">当前项目使用智能生图链路。系统会在镜头文案基础上自动补足构图、光线、连续性和画质增强提示，并在最终成片里加入轻微运镜与更自然的镜头转场；如果某个镜头效果不满意，可以单独重生成。</div>
      <div class="row search-head">
        <div>
          <div class="muted label-strong">当前镜头智能生图</div>
          <div class="muted small-top-gap">直接按当前镜头的分镜提示重新生成图片，系统会自动附加镜头级增强描述。</div>
        </div>
        <div class="row">
          <button class="btn" :disabled="model.busy" @click="model.generateSceneImage">重新生成当前镜头</button>
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

.short-copy {
  line-height: 1.45;
}

.search-head {
  justify-content: space-between;
  align-items: end;
}

.scenePreview {
  width: 100%;
  max-width: 100%;
  display: block;
  object-fit: cover;
  border-radius: 8px;
  height: auto;
}
</style>
