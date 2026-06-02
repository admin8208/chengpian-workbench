<script setup lang="ts">
import AiSceneDetailPanel from './AiSceneDetailPanel.vue'
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
  busy: boolean
  startImages: () => Promise<void>
  sceneQueueModel: any
  sceneDetail: any
}

defineProps<{ model: StoryboardStepModel }>()
</script>

<template>
  <StepPanel
    v-if="model.currentStep === 'media'"
    title="智能出图质检台"
    desc="先修缺镜头图和重复素材，再去看最终成片。"
    step-key="media"
    :is-active="model.currentStep === 'media'"
    :is-completed="model.isCompleted"
    :is-current="model.autoStep === 'media'"
    :status="model.stepStatus"
    :summary="`${model.sceneCount} 镜头 · ${model.missingCount + model.duplicateCount} 个画面问题`"
    :default-expanded="model.currentStep === 'media'"
    style="margin-top: 16px"
  >
    <div class="step-content-inner" id="scene-qc-panel">
      <div class="row" style="justify-content: space-between; align-items: start; gap: 12px; margin-bottom: 16px">
        <div class="row">
          <div class="pill bad">缺镜头图 {{ model.missingCount }}</div>
          <div class="pill">重复素材 {{ model.duplicateCount }}</div>
          <div class="pill ok">智能生图链路模式</div>
        </div>
        <div class="row">
          <button class="btn" :disabled="model.busy" @click="model.startImages">批量生成全部镜头</button>
        </div>
      </div>

      <div class="grid2 sceneQcLayout">
        <ProjectSceneQueuePanel :model="model.sceneQueueModel" />
        <AiSceneDetailPanel :model="model.sceneDetail" />
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
