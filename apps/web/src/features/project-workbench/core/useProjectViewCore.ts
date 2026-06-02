import { computed } from 'vue'
import { useProjectJobPolling } from './useProjectJobPolling'
import { useProjectVideoOutputs } from './useProjectVideoOutputs'
import { useProjectRefresh } from './useProjectRefresh'
import { useProjectTaskActions } from './useProjectTaskActions'
import { useSubtitlePreview } from './useSubtitlePreview'
import { useProjectDisplayJob } from './useProjectDisplayJob'
import { useProjectRunActions } from './useProjectRunActions'
import { useProjectAutosave } from './useProjectAutosave'
import { useProjectLoader } from './useProjectLoader'
import { useProjectSceneSelection } from './useProjectSceneSelection'
import { useProjectTtsViewModel } from './useProjectTtsViewModel'
import { useProjectState } from './useProjectState'
import { useProjectPageActions } from './useProjectPageActions'
import { handleNoFinalNotice, parseJobPayload, refreshProjectTaskState } from './projectViewHelpers'
import { useProjectViewLifecycle } from './useProjectViewLifecycle'
import { useProjectViewModels } from './useProjectViewModels'
import { createNoopProjectActionAdapter, type ProjectViewPlugin } from '../plugins/projectViewPlugin'
import { useProjectViewActions } from './useProjectViewActions'


export function useProjectViewCore(options: {
  plugin: ProjectViewPlugin
}) {
  const { plugin } = options
  const { useFlow, useSceneWorkspace, diagnosticsProvider, createActionAdapter, uiLabels } = plugin
  let resetVideoOutputState: () => void = () => {}
  const state = useProjectState({ resetVideoOutputState: () => resetVideoOutputState() })
  const {
    route,
    router,
    projectId,
    project,
    loadState,
    loadMessage,
    projectAssets,
    runtime,
    summary,
    quality,
    busy,
    err,
    info,
    qualityLoading,
    qualityNotice,
    currentStep,
    manualStepOverride,
    projectJobs,
    autopilotJobs,
    mediaProviderStatus,
    assetById,
    materialMode,
    inputMode,
    projectAspect,
    generatedScript,
    primaryActionLabel,
    confirmActionLabel,
    canConfirmScript,
    showScriptConfirmActions,
    resetProjectState,
    setLoadFailure,
  } = state

  const {
    selectedSceneId,
    selectedScene,
    patchSceneLocal,
    ensureSelectedScene,
    resetSelectedScene,
  } = useProjectSceneSelection({ project })

  const { subtitlePreviewText, subtitlePreviewBusy, subtitlePreviewErr } = useSubtitlePreview(computed(() => project.value?.subtitle_url))

  const {
    saveErr,
    autosaving,
    titleInput,
    sourceInput,
    hydrateProjectInputs,
    clearAutosaveTimers,
  } = useProjectAutosave({ projectId, project })

  const {
    setTtsStatus,
    projectVoiceRateLabel,
    currentTtsBackendLabel,
    currentTtsVoiceLabel,
  } = useProjectTtsViewModel({ projectId, project, err, info })

  let ensureRenderReady: (actionLabel: string) => boolean = () => true
  let actionAdapter = createNoopProjectActionAdapter()
  const flowActionAdapter = {
    continueAutopilot: async () => await actionAdapter.continueAutopilot(),
    startAutofill: async () => await actionAdapter.startAutofill(),
    startImages: async () => await actionAdapter.startImages(),
    startRender: async () => await actionAdapter.startRender(),
    focusSceneIssues: () => actionAdapter.focusSceneIssues(),
  }

  const {
    stepIndex,
    stepFromJobKind,
    stepFromStage,
    recommendedStep,
    goStep,
    proceedToNext,
  } = useFlow({
    project,
    runtime,
    summary,
    currentStep,
    manualStepOverride,
    materialMode,
    info,
    router,
    actions: flowActionAdapter,
  })

  const {
    exportVideos,
    selectedVideoUrl,
    selectedVideoAsset,
    userSelectedVideo,
    finalStatus,
    resetVideoOutputState: resetVideoOutputsState,
    applyAutoSelectedVideo,
    preserveSelectionAfterAssetsRefresh,
  } = useProjectVideoOutputs({ projectAssets })
  resetVideoOutputState = resetVideoOutputsState

  let refreshAssetsOnly: () => Promise<void> = async () => {}
  let refreshSummaryOnly: () => Promise<void> = async () => {}
  let refreshQualityOnly: () => Promise<void> = async () => {}

  const {
    displayJob,
    displaySubstageLabel,
    displayStageSummary,
    displayFailedStageSummary,
    flowNavJobStatus,
    isGeneratingScript,
    canProceed,
    canContinueAutopilot,
    continueLabel,
    canRerunAutopilot,
    jobNeedsLlm,
    jobNeedsImage,
    jobNeedsMedia,
    jobNeedsTts,
    autoStep,
  } = useProjectDisplayJob({
    project,
    runtime,
    summary,
    autopilotJobs,
    currentStep,
    diagnosticsProvider,
    parseJobPayload,
    recommendedStep,
    stepFromJobKind,
    stepFromStage,
  })

  const {
    sortJobsByUpdatedDesc,
    syncAutopilotJobsFromProjectJobs,
    patchLocalJobState,
    stopPolling,
    startPolling,
    refreshPollingByCurrentJobs,
  } = useProjectJobPolling({
    projectJobs,
    autopilotJobs,
    info,
    refreshAssetsOnly: () => refreshAssetsOnly(),
    refreshSummaryOnly: () => refreshSummaryOnly(),
    load: async () => await load(),
  })

  const {
    downloadAsset,
    uploadProjectVoice,
    saveProjectScript,
    copyJobError,
    loadProjectJobs,
  } = useProjectPageActions({
    projectId,
    project,
    projectJobs,
    autopilotJobs,
    busy,
    err,
    info,
    sortJobsByUpdatedDesc,
    syncAutopilotJobsFromProjectJobs,
    load: async () => await load(),
  })

  ;({
    refreshAssetsOnly,
    refreshSummaryOnly,
    refreshQualityOnly,
  } = useProjectRefresh({
    projectId,
    project,
    runtime,
    summary,
    quality,
    qualityLoading,
    qualityNotice,
    projectAssets,
    selectedVideoUrl,
    userSelectedVideo,
    finalStatus,
    exportVideos,
    ensureSelectedScene,
    preserveSelectionAfterAssetsRefresh,
    onRefreshError: (message) => {
      if (!String(message || '').trim()) return
      err.value = `同步项目状态失败：${message}`
    },
  }))

  const runActions = useProjectRunActions({
    projectId,
    selectedScene,
    project,
    busy,
    err,
    info,
    manualStepOverride,
    autopilotJobs,
    projectJobs,
    refreshSummaryOnly,
    startPolling,
    ensureRenderReady: (actionLabel?: string) => ensureRenderReady(actionLabel || ''),
  })

  const { retryTask } = useProjectTaskActions({
    err,
    continueAutopilot: runActions.continueAutopilot,
    loadProjectJobs,
    refreshProjectTaskState: async () => await refreshProjectTaskState({ refreshSummaryOnly, loadProjectJobs }),
    refreshPollingByCurrentJobs,
    patchLocalJobState,
    startPolling,
    stopPolling,
  })

  const { load, retryLoad, invalidateLoad } = useProjectLoader({
    projectId,
    project,
    projectAssets,
    runtime,
    summary,
    quality,
    qualityNotice,
    mediaProviderStatus,
    loadState,
    loadMessage,
    err,
    hydrateProjectInputs,
    ensureSelectedScene,
    resetProjectState,
    setLoadFailure,
    setFinalStatus: (status: any) => {
      finalStatus.value = status
    },
    setTtsStatus,
    loadProjectJobs,
    applyAutoSelectedVideo,
    refreshQualityOnly,
    onLoaded: () => {
      manualStepOverride.value = false
      currentStep.value = autoStep.value
    },
  })

  const sceneWorkspace = useSceneWorkspace({
    projectId,
    project,
    selectedSceneId,
    selectedScene,
    materialMode,
    projectAspect,
    mediaProviderStatus,
    assetById,
    patchSceneLocal,
    refreshAssetsOnly: () => refreshAssetsOnly(),
    refreshSummaryOnly: () => refreshSummaryOnly(),
    busy,
    err,
    info,
    goStep,
  })
  ensureRenderReady = sceneWorkspace.ensureRenderReady
  actionAdapter = createActionAdapter({ runActions, focusSceneIssues: sceneWorkspace.focusSceneIssues })

  const {
    confirmScriptAndRunAutopilot: confirmScriptAndRunAutopilotAction,
    generateSceneImage,
    useHistoryAsset,
    retryDisplayJob,
    copyDisplayJobError,
  } = useProjectViewActions({
    generatedScript,
    displayJob,
    confirmScriptAndRunAutopilotBase: runActions.confirmScriptAndRunAutopilot,
    startScenePrimaryActionBase: async () => await actionAdapter.startScenePrimaryAction(),
    useSceneHistoryAssetBase: sceneWorkspace.useSceneHistoryAsset,
    retryTaskBase: retryTask,
    copyJobErrorBase: copyJobError,
  })

  const {
    inputStepModel,
    sceneDetailModel,
    sceneQueueModel,
    renderStepModel,
    voiceStepModel,
    flowControlModel,
  } = useProjectViewModels({
    titleInput,
    sourceInput,
    autosaving,
    generatedScript,
    isGeneratingScript,
    inputMode,
    project,
    canConfirmScript,
    saveProjectScript,
    confirmScriptAndRunAutopilot: confirmScriptAndRunAutopilotAction,
    uploadProjectVoice,
    selectedScene,
    selectedSceneTags: sceneWorkspace.selectedSceneTags,
    materialMode,
    busy,
    currentScenePreview: sceneWorkspace.currentScenePreview,
    currentSceneAsset: sceneWorkspace.currentSceneAsset,
    suggestBusy: sceneWorkspace.suggestBusy,
    suggestErr: sceneWorkspace.suggestErr,
    suggestItems: sceneWorkspace.suggestItems,
    suggestProvider: sceneWorkspace.suggestProvider,
    suggestKind: sceneWorkspace.suggestKind,
    suggestKindOptions: sceneWorkspace.suggestKindOptions,
    sceneHistoryBusy: sceneWorkspace.sceneHistoryBusy,
    sceneHistoryErr: sceneWorkspace.sceneHistoryErr,
    visibleSceneHistoryAssets: sceneWorkspace.visibleSceneHistoryAssets,
    suggestPreviewUrl: sceneWorkspace.suggestPreviewUrl,
    suggestPreviewKind: sceneWorkspace.suggestPreviewKind,
    sceneAssetType: sceneWorkspace.sceneAssetType,
    patchSceneNarration: async (value: string) => await sceneWorkspace.patchScene({ narration: value }),
    patchSceneImagePrompt: async (value: string) => await sceneWorkspace.patchScene({ image_prompt: value }),
    patchSceneMediaQuery: async (value: string) => await sceneWorkspace.patchScene({ media_query: value }),
    patchSceneDuration: async (value: number) => await sceneWorkspace.patchScene({ duration_sec: value }),
    generateSceneImage,
    loadSuggestions: sceneWorkspace.loadSuggestions,
    importAndBind: sceneWorkspace.importAndBind,
    useHistoryAsset,
    downloadAsset,
    sceneQueue: sceneWorkspace.sceneQueue,
    selectedSceneId,
    sceneIssueStats: sceneWorkspace.sceneIssueStats,
    issueScenes: sceneWorkspace.issueScenes,
    sceneIssueTags: sceneWorkspace.sceneIssueTags,
    focusSceneIssues: sceneWorkspace.focusSceneIssues,
    exportVideos,
    selectedVideoAsset,
    selectedVideoUrl,
    finalStatus,
    projectVoiceRateLabel,
    currentTtsBackendLabel,
    currentTtsVoiceLabel,
    subtitlePreviewText,
    subtitlePreviewBusy,
    subtitlePreviewErr,
    router,
    primaryActionLabel,
    confirmActionLabel,
    showScriptConfirmActions,
    canContinueAutopilot,
    continueLabel,
    canRerunAutopilot,
    currentStep,
    autoStep,
    displayJob,
    displayStageSummary,
    displaySubstageLabel,
    displayFailedStageSummary,
    flowNavJobStatus,
    canProceed,
    finalStatusForFlow: finalStatus,
    summary,
    uiLabels,
    jobNeedsLlm,
    jobNeedsImage,
    jobNeedsMedia,
    jobNeedsTts,
    runAutopilot: runActions.runAutopilot,
    continueAutopilot: runActions.continueAutopilot,
    rerunAutopilot: runActions.rerunAutopilot,
    retryDisplayJob,
    copyJobError: copyDisplayJobError,
    goStep,
    proceedToNext,
  })

  useProjectViewLifecycle({
    projectId,
    autoStep,
    currentStep,
    manualStepOverride,
    autopilotJobs,
    projectJobs,
    suggestItems: sceneWorkspace.suggestItems,
    suggestErr: sceneWorkspace.suggestErr,
    sceneHistoryAssets: sceneWorkspace.sceneHistoryAssets,
    sceneHistoryErr: sceneWorkspace.sceneHistoryErr,
    invalidateLoad,
    stopPolling,
    resetSelectedScene,
    retryLoad,
    load,
    clearAutosaveTimers,
    afterLoad: async () => {
      await handleNoFinalNotice({ route, router, info })
    },
  })

  return {
    router,
    project,
    loadState,
    loadMessage,
    busy,
    err,
    info,
    currentStep,
    saveErr,
    inputStep: inputStepModel,
    sceneIssueStats: sceneWorkspace.sceneIssueStats,
    sceneDetail: sceneDetailModel,
    sceneQueueModel,
    renderStep: renderStepModel,
    voiceStep: voiceStepModel,
    flowControl: flowControlModel,
    stepIndex,
    finalStatus,
    materialMode,
    uiLabels,
    autoStep,
    retryLoad,
    startImages: async () => await actionAdapter.startImages(),
  }
}
