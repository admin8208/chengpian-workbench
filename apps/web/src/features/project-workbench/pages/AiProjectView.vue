<script setup lang="ts">
import AiStoryboardStep from '../../../components/project/AiStoryboardStep.vue'
import SharedProjectLayout from '../components/SharedProjectLayout.vue'
import { useAiProjectView } from '../ai/useAiProjectView'

const vm = useAiProjectView()
</script>

<template>
  <SharedProjectLayout
    :model="{
      ...vm,
      backRoute: '/creator/ai',
    }"
  >
    <template #media="slotProps">
      <AiStoryboardStep
        :model="{
          currentStep: vm.currentStep,
          autoStep: vm.autoStep,
          stepStatus: slotProps.stepStatus,
          isCompleted: vm.stepIndex(vm.currentStep) > 3,
          sceneCount: vm.project?.scenes?.length || 0,
          missingCount: vm.sceneIssueStats.missing,
          duplicateCount: vm.sceneIssueStats.duplicate,
          busy: vm.busy,
          startImages: vm.startImages,
          sceneQueueModel: vm.sceneQueueModel,
          sceneDetail: vm.sceneDetail,
        }"
      />
    </template>
  </SharedProjectLayout>
</template>
