import type { ComputedRef, Ref } from 'vue'
import { api, type Job, type Project, type Scene } from '../../../api'
import { useBaselineRunActions } from './useBaselineRunActions'
import { mergeProjectJobs } from './mergeProjectJobs'
import { usePipelineRunActions } from './usePipelineRunActions'

export function useMixProjectRunActions(options: {
  projectId: ComputedRef<number | null>
  selectedScene: ComputedRef<Scene | null>
  project: Ref<Project | null>
  busy: Ref<boolean>
  err: Ref<string>
  info: Ref<string>
  manualStepOverride: Ref<boolean>
  autopilotJobs: Ref<Job[]>
  projectJobs: Ref<Job[]>
  refreshSummaryOnly: () => Promise<void>
  startPolling: () => void
  ensureRenderReady: (actionLabel?: string) => boolean
}) {
  const { projectId, selectedScene, project, busy, err, info, manualStepOverride, autopilotJobs, projectJobs, refreshSummaryOnly, startPolling, ensureRenderReady } = options

  const { prepareScript } = useBaselineRunActions({ projectId, project, busy, err, info, autopilotJobs, projectJobs, refreshSummaryOnly, startPolling })
  const { confirmScriptAndRunAutopilot, continueAutopilot, rerunAutopilot } = usePipelineRunActions({
    projectId,
    project,
    busy,
    err,
    info,
    manualStepOverride,
    autopilotJobs,
    projectJobs,
    refreshSummaryOnly,
    startPolling,
  })

  async function runAutopilot() {
    if (Number(project.value?.confirmed_baseline_revision_id || 0) > 0) {
      return confirmScriptAndRunAutopilot(String(project.value?.script || ''))
    }
    await prepareScript()
  }

  async function startAutofill() {
    const id = projectId.value
    if (!id) {
      err.value = '项目链接无效，请刷新页面后重试。'
      return
    }
    busy.value = true
    err.value = ''
    try {
      manualStepOverride.value = false
      const res = await api.startAutofillMedia(id, 'video')
      autopilotJobs.value = [res.job]
      projectJobs.value = mergeProjectJobs(projectJobs.value, [res.job])
      startPolling()
    } catch (e: any) {
      err.value = e?.message ?? String(e)
    } finally {
      busy.value = false
    }
  }

  async function startImages() {
    const id = projectId.value
    if (!id) {
      err.value = '项目链接无效，请刷新页面后重试。'
      return
    }
    busy.value = true
    err.value = ''
    try {
      manualStepOverride.value = false
      const res = await api.startImages(id)
      autopilotJobs.value = [res.job]
      projectJobs.value = mergeProjectJobs(projectJobs.value, [res.job])
      startPolling()
    } catch (e: any) {
      err.value = e?.message ?? String(e)
    } finally {
      busy.value = false
    }
  }

  async function startSelectedSceneImage() {
    const scene = selectedScene.value
    if (!scene) return
    busy.value = true
    err.value = ''
    try {
      const res = await api.startSceneImage(scene.id)
      autopilotJobs.value = [res.job]
      projectJobs.value = mergeProjectJobs(projectJobs.value, [res.job])
      startPolling()
    } catch (e: any) {
      err.value = e?.message ?? String(e)
    } finally {
      busy.value = false
    }
  }

  async function startRender() {
    if (!ensureRenderReady('开始渲染')) return
    const id = projectId.value
    if (!id) {
      err.value = '项目链接无效，请刷新页面后重试。'
      return
    }
    busy.value = true
    err.value = ''
    try {
      manualStepOverride.value = false
      const res = await api.startRender(id)
      autopilotJobs.value = [res.job]
      projectJobs.value = mergeProjectJobs(projectJobs.value, [res.job])
      startPolling()
    } catch (e: any) {
      err.value = e?.message ?? String(e)
    } finally {
      busy.value = false
    }
  }

  return {
    prepareScript,
    confirmScriptAndRunAutopilot,
    runAutopilot,
    continueAutopilot,
    rerunAutopilot,
    startAutofill,
    startImages,
    startSelectedSceneImage,
    startRender,
  }
}
