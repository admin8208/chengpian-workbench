<script setup lang="ts">
import type { Asset, ProjectDetail } from '../../api'
import StepPanel from './StepPanel.vue'
import VideoStagePanel from './VideoStagePanel.vue'

type StepStatus = 'error' | 'running' | 'active' | 'pending' | 'completed'

type RenderStepModel = {
  project: ProjectDetail | null
  finalExists: boolean
  finalVideoUrl: string
  exportVideos: Asset[]
  selectedVideoAsset: Asset | null
  selectedVideoUrl: string
  summaryText: string
}

defineProps<{
  currentStep: string
  autoStep: string
  stepStatus: StepStatus
  model: RenderStepModel
}>()

const emit = defineEmits<{
  'update:selectedVideoUrl': [value: string]
}>()
</script>

<template>
  <StepPanel
    v-if="currentStep === 'render'"
    title="最终成片"
    desc="查看最终成片结果。"
    step-key="render"
    :is-active="currentStep === 'render'"
    :is-completed="model.finalExists"
    :is-current="autoStep === 'render'"
    :status="stepStatus"
    :summary="model.summaryText"
    :default-expanded="currentStep === 'render'"
    style="margin-top: 16px"
  >
    <div class="step-content-inner">
      <VideoStagePanel
        :selected-video-url="model.selectedVideoUrl"
        :final-exists="model.finalExists"
        :final-video-url="model.finalVideoUrl"
        :export-videos="model.exportVideos"
        :selected-video-asset="model.selectedVideoAsset"
        @update:selected-video-url="emit('update:selectedVideoUrl', $event)"
      />
    </div>
  </StepPanel>
</template>

<style scoped>
.step-content-inner {
  padding: 20px;
}
</style>
