import type { ComputedRef, Ref } from 'vue'
import { api, type Job, type Project } from '../../../api'
import { mergeProjectJobs } from './mergeProjectJobs'

export function useBaselineRunActions(options: {
  projectId: ComputedRef<number | null>
  project: Ref<Project | null>
  busy: Ref<boolean>
  err: Ref<string>
  info: Ref<string>
  autopilotJobs: Ref<Job[]>
  projectJobs: Ref<Job[]>
  refreshSummaryOnly: () => Promise<void>
  startPolling: () => void
}) {
  const { projectId, project, busy, err, info, autopilotJobs, projectJobs, refreshSummaryOnly, startPolling } = options

  async function prepareScript() {
    const id = projectId.value
    if (!id) {
      err.value = '项目链接无效，请刷新页面后重试。'
      return
    }
    busy.value = true
    err.value = ''
    info.value = ''
    try {
      const res = await api.prepareProjectScript(id)
      autopilotJobs.value = [res.job]
      projectJobs.value = mergeProjectJobs(projectJobs.value, [res.job])
      await refreshSummaryOnly()
      startPolling()
      info.value = String(project.value?.render_config?.input_mode || '').trim().toLowerCase() === 'audio' ? '已开始后台转写，请稍候确认文案。' : '已开始后台生成文案，请稍候确认文案。'
    } catch (e: any) {
      err.value = e?.message ?? String(e)
    } finally {
      busy.value = false
    }
  }

  return { prepareScript }
}
