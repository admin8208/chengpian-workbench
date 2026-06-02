import type { ComputedRef, Ref } from 'vue'
import { api, type Job, type Project } from '../../../api'
import { mergeProjectJobs } from './mergeProjectJobs'

export function usePipelineRunActions(options: {
  projectId: ComputedRef<number | null>
  project: Ref<Project | null>
  busy: Ref<boolean>
  err: Ref<string>
  info: Ref<string>
  manualStepOverride: Ref<boolean>
  autopilotJobs: Ref<Job[]>
  projectJobs: Ref<Job[]>
  refreshSummaryOnly: () => Promise<void>
  startPolling: () => void
}) {
  const { projectId, project, busy, err, info, manualStepOverride, autopilotJobs, projectJobs, refreshSummaryOnly, startPolling } = options

  async function confirmScriptAndRunAutopilot(script?: string) {
    const id = projectId.value
    if (!id) {
      err.value = '项目链接无效，请刷新页面后重试。'
      return
    }
    busy.value = true
    err.value = ''
    info.value = ''
    try {
      const nextProject = await api.confirmProjectScript(id, script)
      project.value = nextProject
      manualStepOverride.value = false
      const res = await api.startAutopilot(id)
      autopilotJobs.value = res.jobs || []
      projectJobs.value = mergeProjectJobs(projectJobs.value, res.jobs || [])
      await refreshSummaryOnly()
      startPolling()
    } catch (e: any) {
      err.value = e?.message ?? String(e)
    } finally {
      busy.value = false
    }
  }

  async function continueAutopilot() {
    const id = projectId.value
    if (!id) {
      err.value = '项目链接无效，请刷新页面后重试。'
      return
    }
    busy.value = true
    err.value = ''
    try {
      manualStepOverride.value = false
      const res = await api.continueAutopilot(id)
      autopilotJobs.value = res.jobs || []
      projectJobs.value = mergeProjectJobs(projectJobs.value, res.jobs || [])
      await refreshSummaryOnly()
      startPolling()
    } catch (e: any) {
      err.value = e?.message ?? String(e)
    } finally {
      busy.value = false
    }
  }

  async function rerunAutopilot() {
    const id = projectId.value
    if (!id) {
      err.value = '项目链接无效，请刷新页面后重试。'
      return
    }
    busy.value = true
    err.value = ''
    try {
      manualStepOverride.value = false
      const res = await api.rerunAutopilot(id)
      autopilotJobs.value = res.jobs || []
      projectJobs.value = mergeProjectJobs(projectJobs.value, res.jobs || [])
      await refreshSummaryOnly()
      startPolling()
    } catch (e: any) {
      err.value = e?.message ?? String(e)
    } finally {
      busy.value = false
    }
  }

  return { confirmScriptAndRunAutopilot, continueAutopilot, rerunAutopilot }
}
