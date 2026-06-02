import { computed, type ComputedRef, type Ref } from 'vue'
import type { Job, ProjectDetail, ProjectRuntime, ProjectSummary } from '../../../api'
import { labelAutopilotStage, labelRenderSubstage } from '../../../labels'
import type { ProjectDiagnosticsProvider } from '../plugins/projectViewPlugin'

type FlowStep = 'input' | 'storyboard' | 'voice' | 'media' | 'render'
type FlowNavJobStatus = 'idle' | 'queued' | 'running' | 'paused' | 'failed' | 'done' | ''

export function useMixProjectDisplayJob(options: {
  project: Ref<ProjectDetail | null>
  runtime: Ref<ProjectRuntime | null>
  summary: Ref<ProjectSummary | null>
  autopilotJobs: Ref<Job[]>
  currentStep: Ref<FlowStep>
  diagnosticsProvider: ProjectDiagnosticsProvider
  parseJobPayload: (job: Job | null | undefined) => any
  recommendedStep: ComputedRef<FlowStep>
  stepFromJobKind: (kind: string | null | undefined) => FlowStep
  stepFromStage: (stage: string | null | undefined) => FlowStep
}) {
  const { project, runtime, summary, autopilotJobs, currentStep, diagnosticsProvider, parseJobPayload, recommendedStep, stepFromJobKind, stepFromStage } = options

  const displayJob = computed(() => {
    const currentJob = autopilotJobs.value.find((job) => !['done', 'failed', 'cancelled'].includes(job.status)) || runtime.value?.current_job || null
    if (currentJob) return currentJob
    if (autopilotJobs.value.length) return autopilotJobs.value[0] || null
    return runtime.value?.summary_job || null
  })

  const displayPayload = computed(() => parseJobPayload(displayJob.value))
  const renderSubstageLabel = computed(() => labelRenderSubstage(displayPayload.value?.render_substage, ''))
  const failedAutopilotStage = computed(() => String(runtime.value?.continue_stage || displayPayload.value?.resume_from_stage || displayPayload.value?.last_failed_stage || summary.value?.continue_stage || '').trim().toLowerCase())
  const displaySubstageLabel = computed(() => {
    if (!displayJob.value) return ''
    return diagnosticsProvider.substageLabel(displayJob.value)
  })
  const displayStageLabel = computed(() => {
    if (!displayJob.value) {
      const stage = labelAutopilotStage(displayPayload.value?.current_stage || failedAutopilotStage.value, '当前阶段')
      return renderSubstageLabel.value ? `${stage} / ${renderSubstageLabel.value}` : stage
    }
    return diagnosticsProvider.mainStageLabel(displayJob.value)
  })
  const displayStageSummary = computed(() => {
    if (!displayJob.value) return displayStageLabel.value
    return diagnosticsProvider.stageSummary(displayJob.value)
  })
  const activeStage = computed(() => String(displayPayload.value?.current_stage || displayPayload.value?.resume_from_stage || displayPayload.value?.last_failed_stage || '').trim().toLowerCase())
  const displayFlowSteps = computed(() => {
    if (!displayJob.value) return []
    return diagnosticsProvider.flowSteps(displayJob.value)
  })
  const displayFailedStageSummary = computed(() => {
    if (!displayJob.value || displayJob.value.status !== 'failed') return ''
    return diagnosticsProvider.failedStageSummary(displayJob.value)
  })
  const summaryJobStatus = computed(() => String(runtime.value?.active_job_status || summary.value?.last_job_status || '').trim().toLowerCase())
  const flowNavJobStatus = computed<FlowNavJobStatus>(() => {
    const status = String(displayJob.value?.status || '').trim().toLowerCase()
    return status === 'idle' || status === 'queued' || status === 'running' || status === 'paused' || status === 'failed' || status === 'done' ? status : ''
  })
  const isGeneratingScript = computed(() => {
    const stage = activeStage.value
    if (String(displayJob.value?.kind || '').trim() === 'script_prepare' && ['queued', 'running'].includes(flowNavJobStatus.value)) return true
    if (stage === 'storyboard' && ['queued', 'running'].includes(flowNavJobStatus.value)) return true
    const message = String(displayJob.value?.message || '').trim()
    return ['queued', 'running'].includes(flowNavJobStatus.value) && (message.includes('脚本') || message.includes('分镜') || message.includes('文案') || message.includes('转写'))
  })
  const canProceed = computed(() => {
    if (flowNavJobStatus.value === 'running') return false
    if (currentStep.value === 'input') {
      const hasConfirmedBaseline = Number(project.value?.confirmed_baseline_revision_id || summary.value?.confirmed_baseline_revision_id || runtime.value?.confirmed_baseline_revision_id || 0) > 0
      return Boolean(project.value?.title?.trim()) && hasConfirmedBaseline
    }
    if (currentStep.value === 'storyboard') return Boolean(project.value?.scenes?.length || 0)
    if (currentStep.value === 'media') return Boolean((summary.value?.missing_asset_count || runtime.value?.missing_asset_count || 0) === 0)
    return true
  })
  const canContinueAutopilot = computed(() => Boolean(failedAutopilotStage.value) && !['queued', 'running', 'paused'].includes(summaryJobStatus.value))
  const continueLabel = computed(() => (failedAutopilotStage.value ? `从${labelAutopilotStage(failedAutopilotStage.value, '当前阶段')}继续` : '继续生成视频'))
  const canRerunAutopilot = computed(() => {
    const status = String(displayJob.value?.status || '').trim().toLowerCase()
    return Boolean(displayJob.value && displayJob.value.kind === 'autopilot' && !['queued', 'running', 'paused'].includes(status))
  })
  const jobNeedsLlm = computed(() => {
    if (String(displayJob.value?.blocking_component || '').trim().toLowerCase() === 'llm') return true
    if (String(displayJob.value?.recommended_action || '').trim().toLowerCase() === 'go_settings_llm') return true
    const message = String(displayJob.value?.message || '')
    return message.includes('大模型') || message.includes('默认服务') || message.includes('服务地址') || message.includes('接口密钥')
  })
  const jobNeedsImage = computed(() => {
    if (String(displayJob.value?.blocking_component || '').trim().toLowerCase() === 'image') return true
    if (String(displayJob.value?.recommended_action || '').trim().toLowerCase() === 'go_settings_image') return true
    const message = String(displayJob.value?.message || '')
    return (message.includes('生图') || message.includes('图片') || message.includes('出图')) && (message.includes('接口密钥') || message.includes('服务地址') || message.includes('模型名称') || message.includes('默认'))
  })
  const jobNeedsMedia = computed(() => {
    if (String(displayJob.value?.blocking_component || '').trim().toLowerCase() === 'media') return true
    if (String(displayJob.value?.recommended_action || '').trim().toLowerCase() === 'go_settings_media') return true
    const message = String(displayJob.value?.message || '')
    return message.includes('素材来源') || message.includes('Pexels') || message.includes('Pixabay') || message.includes('Wikimedia')
  })
  const jobNeedsTts = computed(() => {
    if (String(displayJob.value?.blocking_component || '').trim().toLowerCase() === 'tts') return true
    if (String(displayJob.value?.recommended_action || '').trim().toLowerCase() === 'go_settings_tts') return true
    const message = String(displayJob.value?.message || '')
    return message.includes('在线配音') || message.includes('离线配音') || message.includes('配音') || message.includes('字幕')
  })
  const autoStep = computed<FlowStep>(() => {
    const job = displayJob.value
    if (job && job.status !== 'done' && job.status !== 'failed' && job.status !== 'cancelled') {
      if (job.kind === 'autopilot') {
        const stage = activeStage.value
        if (stage) return stepFromStage(stage)
      }
      return stepFromJobKind(job.kind)
    }
    if (job && job.status === 'failed') {
      if (jobNeedsLlm.value) return 'input'
      if (jobNeedsImage.value) return 'media'
      if (jobNeedsMedia.value) return 'media'
      if (jobNeedsTts.value) return 'voice'
      if (job.kind === 'autopilot') {
        const stage = activeStage.value
        if (stage) return stepFromStage(stage)
      }
      return stepFromJobKind(job.kind)
    }
    if (!job && failedAutopilotStage.value) return stepFromStage(failedAutopilotStage.value)
    return recommendedStep.value
  })

  return {
    displayJob,
    displayPayload,
    renderSubstageLabel,
    displaySubstageLabel,
    displayStageLabel,
    displayStageSummary,
    displayFlowSteps,
    displayFailedStageSummary,
    failedAutopilotStage,
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
  }
}
