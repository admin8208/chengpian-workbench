import type { Ref } from 'vue'

export function useProjectViewActions(options: {
  generatedScript: Ref<string>
  displayJob: Ref<any>
  confirmScriptAndRunAutopilotBase: (script?: string) => Promise<void>
  startScenePrimaryActionBase: () => Promise<void>
  useSceneHistoryAssetBase: (assetId: number) => Promise<void>
  retryTaskBase: (job: any) => Promise<void>
  copyJobErrorBase: (message: string) => Promise<void>
}) {
  const {
    generatedScript,
    displayJob,
    confirmScriptAndRunAutopilotBase,
    startScenePrimaryActionBase,
    useSceneHistoryAssetBase,
    retryTaskBase,
    copyJobErrorBase,
  } = options

  async function confirmScriptAndRunAutopilot() {
    await confirmScriptAndRunAutopilotBase(generatedScript.value)
  }

  async function generateSceneImage() {
    await startScenePrimaryActionBase()
  }

  async function useHistoryAsset(assetId: number) {
    await useSceneHistoryAssetBase(assetId)
  }

  async function retryDisplayJob() {
    if (displayJob.value) await retryTaskBase(displayJob.value)
  }

  async function copyDisplayJobError() {
    await copyJobErrorBase(String(displayJob.value?.message || ''))
  }

  return {
    confirmScriptAndRunAutopilot,
    generateSceneImage,
    useHistoryAsset,
    retryDisplayJob,
    copyDisplayJobError,
  }
}
