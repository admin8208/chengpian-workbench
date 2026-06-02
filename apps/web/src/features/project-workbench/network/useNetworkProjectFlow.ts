import { computed, type ComputedRef, type Ref } from 'vue'
import type { Router } from 'vue-router'
import type { ProjectDetail, ProjectRuntime, ProjectSummary } from '../../../api'

type FlowStep = 'input' | 'storyboard' | 'voice' | 'media' | 'render'

export function useNetworkProjectFlow(options: {
  project: Ref<ProjectDetail | null>
  runtime: Ref<ProjectRuntime | null>
  summary: Ref<ProjectSummary | null>
  currentStep: Ref<FlowStep>
  manualStepOverride: Ref<boolean>
  materialMode: ComputedRef<'ai' | 'network'>
  info: Ref<string>
  router: Router
  actions: {
    continueAutopilot: () => Promise<void>
    startAutofill: () => Promise<void>
    startImages: () => Promise<void>
    startRender: () => Promise<void>
    focusSceneIssues: () => void
  }
}) {
  const { project, runtime, summary, currentStep, manualStepOverride, info, router, actions } = options
  const inputMode = computed<'text' | 'audio'>(() => {
    const raw = String(project.value?.render_config?.input_mode || '').trim().toLowerCase()
    return raw === 'audio' ? 'audio' : 'text'
  })
  function stepIndex(step: FlowStep) {
    const steps: FlowStep[] = ['input', 'storyboard', 'voice', 'media', 'render']
    return Math.max(0, steps.indexOf(step))
  }
  function stepFromJobKind(kind: string | null | undefined): FlowStep {
    const k = String(kind || '').trim()
    if (k === 'script_prepare') return 'input'
    if (k === 'storyboard' || k === 'rewrite') return 'storyboard'
    if (k === 'autofill_media') return 'media'
    if (k === 'tts_offline_install' || k === 'tts_offline_install_all_compatible') return 'voice'
    if (k === 'render' || k === 'autopilot') return 'render'
    return 'input'
  }
  function stepFromStage(stage: string | null | undefined): FlowStep {
    const s = String(stage || '').trim().toLowerCase()
    if (s === 'storyboard') return 'storyboard'
    if (s === 'media') return 'media'
    if (s === 'tts') return 'voice'
    if (s === 'render') return 'render'
    return 'input'
  }
  const recommendedStep = computed<FlowStep>(() => {
    if (inputMode.value === 'audio' && !project.value?.voice_url) return 'input'
    const hasConfirmedBaseline = Number(project.value?.confirmed_baseline_revision_id || summary.value?.confirmed_baseline_revision_id || runtime.value?.confirmed_baseline_revision_id || 0) > 0
    if (!hasConfirmedBaseline) return 'input'
    if (!project.value?.scenes?.length) return 'storyboard'
    if ((runtime.value?.missing_asset_count || summary.value?.missing_asset_count || 0) > 0) return 'media'
    const lastMsg = String(runtime.value?.last_job_message || summary.value?.last_job_message || '')
    if (lastMsg.includes('字幕') || lastMsg.includes('配音') || lastMsg.includes('音频')) return 'voice'
    if (lastMsg.includes('素材') || lastMsg.includes('匹配') || lastMsg.includes('修复')) return 'media'
    return 'render'
  })
  function goStep(step: FlowStep, manual = false) {
    if (manual) manualStepOverride.value = true
    currentStep.value = step
  }
  const supportedFixActions = computed(() => {
    const allowed = new Set(['render', 'continue_from_project', 'autofill_media', 'focus_scene_issues', 'go_settings_llm', 'go_settings_media', 'go_settings_tts'])
    return (runtime.value?.suggested_fix_actions || summary.value?.fix_actions || []).filter((action: string) => allowed.has(String(action))).slice(0, 4)
  })
  async function runFixAction(action: string) {
    const a = String(action || '').trim()
    if (!a) return
    if (a === 'render') return actions.startRender()
    if (a === 'continue_from_project') return actions.continueAutopilot()
    if (a === 'autofill_media') return actions.startAutofill()
    if (a === 'focus_scene_issues') return actions.focusSceneIssues()
    if (a === 'go_settings_llm') return router.push({ path: '/settings', query: { tab: 'llm' } })
    if (a === 'go_settings_media') return router.push({ path: '/settings', query: { tab: 'media' } })
    if (a === 'go_settings_tts') return router.push({ path: '/settings', query: { tab: 'tts' } })
    info.value = '当前项目使用素材创作工作流，请直接处理素材匹配问题。'
  }
  function proceedToNext() {
    const steps: FlowStep[] = ['input', 'storyboard', 'voice', 'media', 'render']
    const currentIndex = steps.indexOf(currentStep.value)
    if (currentIndex < steps.length - 1) {
      const nextStep = steps[currentIndex + 1]
      if (nextStep) goStep(nextStep, true)
    }
  }
  return { stepIndex, stepFromJobKind, stepFromStage, recommendedStep, goStep, supportedFixActions, runFixAction, proceedToNext }
}
