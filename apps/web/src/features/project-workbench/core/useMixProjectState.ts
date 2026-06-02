import { computed, ref, type ComputedRef, type Ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import type { Asset, Job, MediaProviderStatus, ProjectDetail, ProjectQuality, ProjectRuntime, ProjectSummary } from '../../../api'
import { defaultDimensionsForAspect, normalizeAspect, type RenderAspect } from '../../../renderConfig'

export type FlowStep = 'input' | 'storyboard' | 'voice' | 'media' | 'render'

type UseMixProjectStateArgs = {
  resetVideoOutputState: () => void
}

type UseMixProjectStateResult = {
  route: ReturnType<typeof useRoute>
  router: ReturnType<typeof useRouter>
  projectId: ComputedRef<number | null>
  project: Ref<ProjectDetail | null>
  loadState: Ref<'loading' | 'ready' | 'error' | 'not_found'>
  loadMessage: Ref<string>
  projectAssets: Ref<Asset[]>
  runtime: Ref<ProjectRuntime | null>
  summary: Ref<ProjectSummary | null>
  quality: Ref<ProjectQuality | null>
  busy: Ref<boolean>
  err: Ref<string>
  info: Ref<string>
  qualityLoading: Ref<boolean>
  qualityNotice: Ref<string>
  currentStep: Ref<FlowStep>
  manualStepOverride: Ref<boolean>
  projectJobs: Ref<Job[]>
  autopilotJobs: Ref<Job[]>
  mediaProviderStatus: Ref<MediaProviderStatus[]>
  assetById: ComputedRef<Map<number, Asset>>
  materialMode: ComputedRef<'ai' | 'network'>
  inputMode: ComputedRef<'text' | 'audio'>
  projectAspect: ComputedRef<RenderAspect>
  generatedScript: ComputedRef<string>
  hasConfirmedBaseline: ComputedRef<boolean>
  primaryActionLabel: ComputedRef<string>
  confirmActionLabel: ComputedRef<string>
  canConfirmScript: ComputedRef<boolean>
  showScriptConfirmActions: ComputedRef<boolean>
  resetProjectState: () => void
  isProjectMissingMessage: (message: string) => boolean
  setLoadFailure: (message: string) => void
}

export function useMixProjectState({ resetVideoOutputState }: UseMixProjectStateArgs): UseMixProjectStateResult {
  const route = useRoute()
  const router = useRouter()

  const projectId = computed<number | null>(() => {
    const raw = Number(route.params.id)
    return Number.isInteger(raw) && raw > 0 ? raw : null
  })
  const project = ref<ProjectDetail | null>(null)
  const loadState = ref<'loading' | 'ready' | 'error' | 'not_found'>('loading')
  const loadMessage = ref('正在加载项目…')

  const projectAssets = ref<Asset[]>([])
  const runtime = ref<ProjectRuntime | null>(null)
  const summary = ref<ProjectSummary | null>(null)
  const quality = ref<ProjectQuality | null>(null)

  const busy = ref(false)
  const err = ref('')
  const info = ref('')
  const qualityLoading = ref(false)
  const qualityNotice = ref('')

  const currentStep = ref<FlowStep>('input')
  const manualStepOverride = ref(false)

  const projectJobs = ref<Job[]>([])
  const autopilotJobs = ref<Job[]>([])
  const mediaProviderStatus = ref<MediaProviderStatus[]>([])

  const assetById = computed(() => {
    const map = new Map<number, Asset>()
    for (const asset of projectAssets.value) {
      if (typeof asset.id === 'number') map.set(asset.id, asset)
    }
    return map
  })

  const materialMode = computed<'ai' | 'network'>(() => {
    const raw = String(project.value?.render_config?.material_mode || '').trim().toLowerCase()
    return raw === 'ai' ? 'ai' : 'network'
  })

  const inputMode = computed<'text' | 'audio'>(() => {
    const raw = String(project.value?.render_config?.input_mode || '').trim().toLowerCase()
    return raw === 'audio' ? 'audio' : 'text'
  })

  const projectAspect = computed<RenderAspect>(() => normalizeAspect(project.value?.render_config?.aspect || defaultDimensionsForAspect('landscape').aspect))

  const generatedScript = computed(() => String(project.value?.script || '').trim())
  const hasConfirmedBaseline = computed(() => Number(project.value?.confirmed_baseline_revision_id || summary.value?.confirmed_baseline_revision_id || runtime.value?.confirmed_baseline_revision_id || 0) > 0)
  const primaryActionLabel = computed(() => {
    if (hasConfirmedBaseline.value) return '生成视频'
    if (generatedScript.value.trim()) return inputMode.value === 'audio' ? '重新识别转写' : '重新生成文案'
    return inputMode.value === 'audio' ? '识别转写' : '生成文案'
  })
  const confirmActionLabel = computed(() => inputMode.value === 'audio' ? '确认转写并生成视频' : '确认文案并生成视频')
  const canConfirmScript = computed(() => Boolean(generatedScript.value.trim()))
  const showScriptConfirmActions = computed(() => !hasConfirmedBaseline.value && canConfirmScript.value)

  function resetProjectState() {
    project.value = null
    projectAssets.value = []
    runtime.value = null
    summary.value = null
    quality.value = null
    qualityLoading.value = false
    qualityNotice.value = ''
    autopilotJobs.value = []
    projectJobs.value = []
    resetVideoOutputState()
  }

  function isProjectMissingMessage(message: string) {
    const text = String(message || '').trim()
    return text.includes('项目不存在') || text.includes('404')
  }

  function setLoadFailure(message: string) {
    resetProjectState()
    const missing = isProjectMissingMessage(message)
    loadMessage.value = missing ? '这个项目可能刚刚被删除，或者当前链接已经失效。' : (message || '项目加载失败。')
    loadState.value = missing ? 'not_found' : 'error'
  }

  return {
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
    hasConfirmedBaseline,
    primaryActionLabel,
    confirmActionLabel,
    canConfirmScript,
    showScriptConfirmActions,
    resetProjectState,
    isProjectMissingMessage,
    setLoadFailure,
  }
}
