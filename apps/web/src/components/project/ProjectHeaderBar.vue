<script setup lang="ts">
import { labelStatus } from '../../labels'

type HeaderModel = {
  project: { title?: string; status?: string } | null
  titleInput: string
  back: () => void
}

defineProps<{
  model: HeaderModel
}>()
</script>

<template>
  <header class="project-header">
    <div class="header-left">
      <button class="btnGhost" @click="model.back()">← 返回创作中心</button>
      <div class="header-title">{{ model.titleInput.trim() || model.project?.title || '' }}</div>
      <div class="header-tags">
        <div class="pill" :class="{ ok: model.project?.status === 'ready', run: model.project?.status === 'processing', bad: model.project?.status === 'failed' }">
          {{ labelStatus(model.project?.status || '') }}
        </div>
      </div>
    </div>
  </header>
</template>

<style scoped>
.project-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  padding: 16px 20px;
  background: rgba(255, 255, 255, 0.95);
  border-radius: 20px;
  border: 1px solid var(--line);
  margin-bottom: 16px;
  position: sticky;
  top: 0;
  z-index: 100;
  flex-wrap: wrap;
}

html.dark .project-header {
  background: rgba(30, 41, 59, 0.95);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.header-title {
  font-size: 18px;
  font-weight: 800;
  letter-spacing: -0.02em;
}

.header-tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

@media (max-width: 768px) {
  .project-header {
    flex-direction: column;
    align-items: stretch;
  }

  .header-left {
    justify-content: flex-start;
  }
}
</style>
