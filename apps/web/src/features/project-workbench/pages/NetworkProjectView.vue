<script setup lang="ts">
import NetworkStoryboardStep from '../../../components/project/NetworkStoryboardStep.vue'
import SharedProjectLayout from '../components/SharedProjectLayout.vue'
import { useNetworkProjectView } from '../network/useNetworkProjectView'

const vm = useNetworkProjectView()
</script>

<template>
  <SharedProjectLayout
    :model="{
      ...vm,
      backRoute: '/creator/network',
    }"
  >
    <template #media="slotProps">
      <NetworkStoryboardStep
        :model="{
          currentStep: vm.currentStep,
          autoStep: vm.autoStep,
          stepStatus: slotProps.stepStatus,
          isCompleted: vm.stepIndex(vm.currentStep) > 3,
          sceneCount: vm.project?.scenes?.length || 0,
          missingCount: vm.sceneIssueStats.missing,
          duplicateCount: vm.sceneIssueStats.duplicate,
          sceneQueueModel: vm.sceneQueueModel,
          sceneDetail: vm.sceneDetail,
        }"
      />
    </template>
  </SharedProjectLayout>
</template>
