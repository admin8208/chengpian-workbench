import { onMounted, onUnmounted, watch, type Ref } from 'vue'

export function useProjectViewLifecycle(options: {
  projectId: Ref<number | null>
  autoStep: Ref<'input' | 'storyboard' | 'voice' | 'media' | 'render'>
  currentStep: Ref<'input' | 'storyboard' | 'voice' | 'media' | 'render'>
  manualStepOverride: Ref<boolean>
  autopilotJobs: Ref<any[]>
  projectJobs: Ref<any[]>
  suggestItems: Ref<any[]>
  suggestErr: Ref<string>
  sceneHistoryAssets: Ref<any[]>
  sceneHistoryErr: Ref<string>
  invalidateLoad: () => void
  stopPolling: () => void
  resetSelectedScene: () => void
  retryLoad: () => void
  load: () => Promise<void>
  clearAutosaveTimers: () => void
  afterLoad: () => Promise<void>
}) {
  const {
    projectId,
    autoStep,
    currentStep,
    manualStepOverride,
    autopilotJobs,
    projectJobs,
    suggestItems,
    suggestErr,
    sceneHistoryAssets,
    sceneHistoryErr,
    invalidateLoad,
    stopPolling,
    resetSelectedScene,
    retryLoad,
    load,
    clearAutosaveTimers,
    afterLoad,
  } = options

  watch(projectId, () => {
    invalidateLoad()
    stopPolling()
    autopilotJobs.value = []
    projectJobs.value = []
    resetSelectedScene()
    suggestItems.value = []
    suggestErr.value = ''
    sceneHistoryAssets.value = []
    sceneHistoryErr.value = ''
    retryLoad()
  })

  watch(
    () => autoStep.value,
    (step) => {
      if (!manualStepOverride.value && currentStep.value !== step) currentStep.value = step
    },
    { immediate: true }
  )

  onMounted(() => {
    load().then(afterLoad).catch(() => {})
  })

  onUnmounted(() => {
    invalidateLoad()
    stopPolling()
    clearAutosaveTimers()
  })
}
