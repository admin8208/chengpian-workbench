<script setup lang="ts">
import type { Scene } from '../../api'

type SceneIssueTag = {
  key: string
  label: string
  tone: string
}

type SceneQueueModel = {
  scenes: Scene[]
  sceneQueue: Scene[]
  selectedSceneId: number | null
  sceneIssueStats: { missing: number; duplicate: number }
  issueSceneCount: number
  busy: boolean
  sceneAssetType: (scene: Scene) => string
  sceneIssueTags: (scene: Scene) => SceneIssueTag[]
  selectScene: (sceneId: number) => void
  focusNextIssue: () => void
}

defineProps<{
  model: SceneQueueModel
}>()
</script>

<template>
  <section class="queue-panel">
    <div class="row queue-head">
      <div class="cardTitle">镜头队列</div>
      <div class="row">
        <div class="pill">{{ model.scenes.length }} 镜头</div>
        <button v-if="model.issueSceneCount > 1" class="btnGhost" :disabled="model.busy" @click="model.focusNextIssue()">跳到下一个问题镜头</button>
      </div>
    </div>
    <div class="muted queue-hint">默认优先把有问题的镜头排在前面，方便连续修复。</div>

    <div v-if="!model.scenes.length" class="muted queue-empty">还没有分镜。点"生成视频"或先生成分镜。</div>
    <div v-else class="queue-list">
      <button
        v-for="scene in model.sceneQueue"
        :key="scene.id"
        class="scene"
        :class="{ active: scene.id === model.selectedSceneId }"
        @click="model.selectScene(scene.id)"
      >
        <div class="idx">{{ String(scene.idx).padStart(2, '0') }}</div>
        <div class="scene-body">
          <div class="txt">{{ scene.narration || '（无旁白）' }}</div>
          <div class="muted scene-meta">{{ scene.duration_sec }}s · {{ model.sceneAssetType(scene) }}</div>
          <div class="row scene-tags">
            <div v-for="tag in model.sceneIssueTags(scene)" :key="`${scene.id}-${tag.key}`" class="pill" :class="tag.tone">{{ tag.label }}</div>
          </div>
        </div>
      </button>
    </div>
  </section>
</template>

<style scoped>
.queue-panel {
  min-width: 0;
}

.queue-head {
  justify-content: space-between;
}

.queue-hint {
  margin-top: 6px;
}

.queue-empty {
  margin-top: 10px;
}

.queue-list {
  margin-top: 10px;
  max-height: 60vh;
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.scene {
  transition: all 0.2s ease;
  border-radius: 8px;
}

.scene:hover {
  background: rgba(0, 0, 0, 0.05);
}

html.dark .scene:hover {
  background: rgba(255, 255, 255, 0.05);
}

.scene.active {
  border-left: 4px solid var(--primary);
}

.scene-body {
  min-width: 0;
}

.scene-meta {
  margin-top: 4px;
}

.scene-tags {
  margin-top: 8px;
}
</style>
