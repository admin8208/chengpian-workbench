import { computed, proxyRefs, type Ref } from 'vue'

export function useProjectViewModels(options: {
  titleInput: Ref<string>
  sourceInput: Ref<string>
  autosaving: Ref<boolean>
  generatedScript: Ref<string>
  isGeneratingScript: Ref<boolean>
  inputMode: Ref<'text' | 'audio'>
  project: Ref<any>
  canConfirmScript: Ref<boolean>
  saveProjectScript: (script: string) => Promise<void>
  confirmScriptAndRunAutopilot: () => Promise<void>
  uploadProjectVoice: (file: File) => Promise<void>
  selectedScene: Ref<any>
  selectedSceneTags: Ref<any>
  materialMode: Ref<'ai' | 'network'>
  busy: Ref<boolean>
  currentScenePreview: Ref<any>
  currentSceneAsset: Ref<any>
  suggestBusy: Ref<boolean>
  suggestErr: Ref<string>
  suggestItems: Ref<any[]>
  suggestProvider: Ref<any>
  suggestKind: Ref<any>
  suggestKindOptions: Ref<any[]>
  sceneHistoryBusy: Ref<boolean>
  sceneHistoryErr: Ref<string>
  visibleSceneHistoryAssets: Ref<any[]>
  suggestPreviewUrl: (item: any) => string
  suggestPreviewKind: (item: any) => string
  sceneAssetType: (scene: any) => string
  patchSceneNarration: (value: string) => Promise<void>
  patchSceneImagePrompt: (value: string) => Promise<void>
  patchSceneMediaQuery: (value: string) => Promise<void>
  patchSceneDuration: (value: number) => Promise<void>
  generateSceneImage: () => Promise<void>
  loadSuggestions: () => Promise<void>
  importAndBind: (item: any) => Promise<void>
  useHistoryAsset: (assetId: number) => Promise<void>
  downloadAsset: (asset: any) => void
  sceneQueue: Ref<any>
  selectedSceneId: Ref<number | null>
  sceneIssueStats: Ref<any>
  issueScenes: Ref<any[]>
  sceneIssueTags: (scene: any) => any[]
  focusSceneIssues: () => void
  exportVideos: Ref<any[]>
  selectedVideoAsset: Ref<any>
  selectedVideoUrl: Ref<string>
  finalStatus: Ref<any>
  projectVoiceRateLabel: Ref<string>
  currentTtsBackendLabel: Ref<string>
  currentTtsVoiceLabel: Ref<string>
  subtitlePreviewText: Ref<string>
  subtitlePreviewBusy: Ref<boolean>
  subtitlePreviewErr: Ref<string>
  router: any
  primaryActionLabel: Ref<string>
  confirmActionLabel: Ref<string>
  showScriptConfirmActions: Ref<boolean>
  canContinueAutopilot: Ref<boolean>
  continueLabel: Ref<string>
  canRerunAutopilot: Ref<boolean>
  currentStep: Ref<'input' | 'storyboard' | 'voice' | 'media' | 'render'>
  autoStep: Ref<'input' | 'storyboard' | 'voice' | 'media' | 'render'>
  displayJob: Ref<any>
  displayStageSummary: Ref<string>
  displaySubstageLabel: Ref<string>
  displayFailedStageSummary: Ref<string>
  flowNavJobStatus: Ref<any>
  canProceed: Ref<boolean>
  finalStatusForFlow: Ref<any>
  summary: Ref<any>
  uiLabels: Ref<any> | any
  jobNeedsLlm: Ref<boolean>
  jobNeedsImage: Ref<boolean>
  jobNeedsMedia: Ref<boolean>
  jobNeedsTts: Ref<boolean>
  runAutopilot: () => Promise<void>
  continueAutopilot: () => Promise<void>
  rerunAutopilot: () => Promise<void>
  retryDisplayJob: () => Promise<void>
  copyJobError: () => Promise<void>
  goStep: (step: 'input' | 'storyboard' | 'voice' | 'media' | 'render', manual?: boolean) => void
  proceedToNext: () => void
}) {
  const inputStepModel = proxyRefs({
    titleInput: options.titleInput,
    sourceInput: options.sourceInput,
    autosaving: options.autosaving,
    generatedScript: options.generatedScript,
    isGeneratingScript: computed(() => options.isGeneratingScript.value),
    inputMode: options.inputMode,
    projectVoiceUrl: computed(() => options.project.value?.voice_url || null),
    hasConfirmedBaseline: computed(() => Number(options.project.value?.confirmed_baseline_revision_id || 0) > 0),
    primaryLabel: options.primaryActionLabel,
    rerunLabel: options.primaryActionLabel,
    busy: options.busy,
    canConfirmScript: options.canConfirmScript,
    runPrimary: async () => await options.runAutopilot(),
    rerunScript: async () => await options.runAutopilot(),
    saveProjectScript: async (script: string) => await options.saveProjectScript(script),
    confirmScriptAndRunAutopilot: async () => await options.confirmScriptAndRunAutopilot(),
    uploadProjectVoice: async (file: File) => await options.uploadProjectVoice(file),
  })

  const sceneDetailModel = proxyRefs({
    selectedScene: options.selectedScene,
    selectedSceneTags: options.selectedSceneTags,
    materialMode: options.materialMode,
    busy: options.busy,
    currentScenePreview: options.currentScenePreview,
    currentSceneAsset: options.currentSceneAsset,
    suggestBusy: options.suggestBusy,
    suggestErr: options.suggestErr,
    suggestItems: options.suggestItems,
    suggestProvider: options.suggestProvider,
    suggestKind: options.suggestKind,
    suggestKindOptions: options.suggestKindOptions,
    sceneHistoryBusy: options.sceneHistoryBusy,
    sceneHistoryErr: options.sceneHistoryErr,
    visibleSceneHistoryAssets: options.visibleSceneHistoryAssets,
    suggestPreviewUrl: options.suggestPreviewUrl,
    suggestPreviewKind: options.suggestPreviewKind,
    sceneAssetType: options.sceneAssetType,
    patchSceneNarration: async (value: string) => await options.patchSceneNarration(value),
    patchSceneImagePrompt: async (value: string) => await options.patchSceneImagePrompt(value),
    patchSceneMediaQuery: async (value: string) => await options.patchSceneMediaQuery(value),
    patchSceneDuration: async (value: number) => await options.patchSceneDuration(value),
    generateSceneImage: async () => await options.generateSceneImage(),
    loadSuggestions: async () => await options.loadSuggestions(),
    importAndBind: async (item: any) => await options.importAndBind(item),
    useHistoryAsset: async (assetId: number) => await options.useHistoryAsset(assetId),
    downloadAsset: options.downloadAsset,
  })

  const sceneQueueModel = proxyRefs({
    scenes: computed(() => options.project.value?.scenes || []),
    sceneQueue: options.sceneQueue,
    selectedSceneId: options.selectedSceneId,
    sceneIssueStats: options.sceneIssueStats,
    issueSceneCount: computed(() => options.issueScenes.value.length),
    busy: options.busy,
    sceneAssetType: options.sceneAssetType,
    sceneIssueTags: options.sceneIssueTags,
    selectScene: (sceneId: number) => {
      options.selectedSceneId.value = sceneId
    },
    focusNextIssue: options.focusSceneIssues,
  })

  const renderStepModel = proxyRefs({
    project: options.project,
    finalExists: computed(() => Boolean(options.finalStatus.value && options.finalStatus.value.exists)),
    finalVideoUrl: computed(() => options.finalStatus.value?.url || ''),
    exportVideos: options.exportVideos,
    selectedVideoAsset: options.selectedVideoAsset,
    selectedVideoUrl: options.selectedVideoUrl,
    summaryText: computed(() => (options.finalStatus.value?.exists ? '已有最终成片' : '等待生成最终成片')),
  })

  const voiceStepModel = proxyRefs({
    project: options.project,
    inputMode: options.inputMode,
    projectVoiceRateLabel: options.projectVoiceRateLabel,
    currentTtsBackendLabel: options.currentTtsBackendLabel,
    currentTtsVoiceLabel: options.currentTtsVoiceLabel,
    subtitlePreviewText: options.subtitlePreviewText,
    subtitlePreviewBusy: options.subtitlePreviewBusy,
    subtitlePreviewErr: options.subtitlePreviewErr,
  })

  const flowControlModel = proxyRefs({
    project: options.project,
    busy: options.busy,
    titleInput: options.titleInput,
    primaryLabel: options.primaryActionLabel,
    secondaryLabel: options.confirmActionLabel,
    showScriptConfirmActions: options.showScriptConfirmActions,
    canContinueAutopilot: options.canContinueAutopilot,
    continueLabel: options.continueLabel,
    showRerun: options.canRerunAutopilot,
    currentStep: options.currentStep,
    recommendedStep: options.autoStep,
    jobStatus: computed(() => String(options.flowNavJobStatus.value || '') as any),
    jobProgress: computed(() => Number(options.displayJob.value?.progress || 0)),
    jobMessage: computed(() => String(options.displayJob.value?.message || '')),
    sceneCount: computed(() => Number(options.project.value?.scenes?.length || 0)),
    missingAssetCount: computed(() => Number(options.summary.value?.missing_asset_count || 0)),
    finalExists: computed(() => Boolean(options.finalStatusForFlow.value && options.finalStatusForFlow.value.exists)),
    canProceed: options.canProceed,
    inputMode: options.inputMode,
    materialMode: options.materialMode,
    uiLabels: options.uiLabels,
    hasConfirmedBaseline: computed(() => Number(options.project.value?.confirmed_baseline_revision_id || 0) > 0),
    hasDraftScript: computed(() => Boolean(String(options.project.value?.script || '').trim()) && Number(options.project.value?.confirmed_baseline_revision_id || 0) <= 0),
    visibleJobBar: computed(() => Boolean(options.displayJob.value)),
    currentStageLabel: options.displayStageSummary,
    currentSubstageLabel: options.displaySubstageLabel,
    statusLabel: computed(() => {
      const status = String(options.displayJob.value?.status || '').trim().toLowerCase()
      if (status === 'queued') return '排队中'
      if (status === 'running') return '执行中'
      if (status === 'paused') return '已暂停'
      if (status === 'failed') return '失败'
      if (status === 'done') return '完成'
      if (status === 'cancelled') return '已取消'
      return '-'
    }),
    failedStageSummary: options.displayFailedStageSummary,
    failed: computed(() => Boolean(options.displayJob.value && String(options.displayJob.value.status || '') === 'failed')),
    jobNeedsLlm: options.jobNeedsLlm,
    jobNeedsImage: options.jobNeedsImage,
    jobNeedsMedia: options.jobNeedsMedia,
    jobNeedsTts: options.jobNeedsTts,
    back: () => {
      options.router.push(options.materialMode.value === 'network' ? '/creator/network' : '/creator/ai')
    },
    runPrimary: async () => {
      if (options.canContinueAutopilot.value) {
        await options.continueAutopilot()
        return
      }
      await options.runAutopilot()
    },
    confirmPrimary: async () => {
      await options.confirmScriptAndRunAutopilot()
    },
    rerun: async () => {
      await options.rerunAutopilot()
    },
    retryCurrentJob: async () => {
      await options.retryDisplayJob()
    },
    copyError: async () => {
      await options.copyJobError()
    },
    goSettings: (tab: 'llm' | 'image' | 'media' | 'tts') => {
      options.router.push({ path: '/settings', query: { tab } })
    },
    goCreatorHome: () => {
      options.router.push(options.materialMode.value === 'network' ? '/creator/network' : '/creator/ai')
    },
    updateCurrentStep: (step: 'input' | 'storyboard' | 'voice' | 'media' | 'render') => {
      options.goStep(step, true)
    },
    proceedToNext: () => {
      options.proceedToNext()
    },
  })

  return {
    inputStepModel,
    sceneDetailModel,
    sceneQueueModel,
    renderStepModel,
    voiceStepModel,
    flowControlModel,
  }
}
