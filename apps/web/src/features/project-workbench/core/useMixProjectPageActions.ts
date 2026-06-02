import type { ComputedRef, Ref } from 'vue'

import { api, type Asset, type Job, type ProjectDetail } from '../../../api'

export function useMixProjectPageActions(options: {
  projectId: ComputedRef<number | null>
  project: Ref<ProjectDetail | null>
  projectJobs: Ref<Job[]>
  autopilotJobs: Ref<Job[]>
  busy: Ref<boolean>
  err: Ref<string>
  info: Ref<string>
  sortJobsByUpdatedDesc: (jobs: Job[]) => Job[]
  syncAutopilotJobsFromProjectJobs: () => void
  load: () => Promise<void>
}) {
  const {
    projectId,
    project,
    projectJobs,
    busy,
    err,
    info,
    sortJobsByUpdatedDesc,
    syncAutopilotJobsFromProjectJobs,
    load,
  } = options

  function downloadAsset(asset: Asset) {
    if (asset.url) window.open(asset.url, '_blank')
  }

  async function uploadProjectVoice(file: File) {
    const id = projectId.value
    if (!id || !project.value) {
      err.value = '项目链接无效，请刷新页面后重试。'
      return
    }
    busy.value = true
    err.value = ''
    info.value = ''
    try {
      const asset = await api.uploadProjectAsset(id, file, 'audio', 'project_source')
      await api.patchProject(id, {
        voice_asset_id: asset.id,
        render_config: {
          ...((project.value.render_config || {}) as any),
          input_mode: 'audio',
        },
      })
      await load()
      info.value = `已绑定主音频：${String(asset.meta?.title || file.name || '音频文件')}`
    } catch (e: any) {
      err.value = e?.message ?? String(e)
    } finally {
      busy.value = false
    }
  }

  async function saveProjectScript(script: string) {
    const id = projectId.value
    if (!id || !project.value) {
      err.value = '项目链接无效，请刷新页面后重试。'
      return
    }
    try {
      const wasConfirmed = Number(project.value.confirmed_baseline_revision_id || 0) > 0
      const next = await api.patchProject(id, { script })
      project.value = { ...project.value, ...next }
      const stillConfirmed = Number(next.confirmed_baseline_revision_id || 0) > 0
      if (wasConfirmed && !stillConfirmed) {
        info.value = '文案已修改，当前已回到待确认状态。请重新确认后再开始生成视频。'
      }
    } catch (e: any) {
      err.value = e?.message ?? String(e)
    }
  }

  async function copyJobError(message: string) {
    const txt = String(message || '')
    if (!txt) return
    try {
      await navigator.clipboard.writeText(txt)
    } catch {
      // ignore
    }
  }

  async function loadProjectJobs(limit = 200) {
    const id = projectId.value
    if (!id) {
      projectJobs.value = []
      syncAutopilotJobsFromProjectJobs()
      return
    }
    const jobs = await api.listJobs(limit)
    projectJobs.value = sortJobsByUpdatedDesc((jobs || []).filter((j) => j.project_id === id))
    syncAutopilotJobsFromProjectJobs()
  }

  return {
    downloadAsset,
    uploadProjectVoice,
    saveProjectScript,
    copyJobError,
    loadProjectJobs,
  }
}
