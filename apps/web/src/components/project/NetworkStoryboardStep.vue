<script setup lang="ts">
import NetworkSceneDetailPanel from './NetworkSceneDetailPanel.vue'
import ProjectSceneQueuePanel from './ProjectSceneQueuePanel.vue'
import StepPanel from './StepPanel.vue'

type StoryboardStepModel = {
  currentStep: 'input' | 'storyboard' | 'voice' | 'media' | 'render'
  autoStep: 'input' | 'storyboard' | 'voice' | 'media' | 'render'
  stepStatus: 'error' | 'running' | 'active' | 'pending' | 'completed'
  isCompleted: boolean
  sceneCount: number
  missingCount: number
  duplicateCount: number
  sceneQueueModel: any
  sceneDetail: any
}

defineProps<{ model: StoryboardStepModel }>()
</script>

<template>
  <StepPanel
    v-if="model.currentStep === 'media'"
    title="素材匹配质检台"
    desc="先修缺素材和重复素材，再去看最终成片。"
    step-key="media"
    :is-active="model.currentStep === 'media'"
    :is-completed="model.isCompleted"
    :is-current="model.autoStep === 'media'"
    :status="model.stepStatus"
    :summary="`${model.sceneCount} 镜头 · ${model.missingCount + model.duplicateCount} 个素材问题`"
    :default-expanded="model.currentStep === 'media'"
    style="margin-top: 16px"
  >
    <div class="step-content-inner" id="scene-qc-panel">
      <div class="row" style="justify-content: space-between; align-items: start; gap: 12px; margin-bottom: 16px">
        <div class="row">
          <div class="pill bad">缺素材 {{ model.missingCount }}</div>
          <div class="pill">重复素材 {{ model.duplicateCount }}</div>
          <div class="pill run">网络素材模式</div>
        </div>
      </div>

      <div class="grid2 sceneQcLayout">
        <ProjectSceneQueuePanel :model="model.sceneQueueModel" />
        <NetworkSceneDetailPanel :model="model.sceneDetail" />
      </div>
    </div>
  </StepPanel>
</template>

<style scoped>
.step-content-inner {
  padding: 20px;
}

.sceneQcLayout {
  gap: 20px;
}
</style>
