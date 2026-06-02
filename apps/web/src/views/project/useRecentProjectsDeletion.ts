import { ref, type ComputedRef, type Ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRouter } from 'vue-router'
import { api, type Project } from '../../api'

export function useRecentProjectsDeletion(options: {
  visibleProjects: ComputedRef<Project[]>
  selectedProjectIds: Ref<number[]>
  selectionMode: Ref<boolean>
  bulkDeleting: Ref<boolean>
  err: Ref<string>
  load: () => Promise<void>
  canDeleteProject: (project: Project) => boolean
  projectDeleteBlockedReason: (project: Project) => string
  projectHasQueuedJob: (project: Project) => boolean
}) {
  const { visibleProjects, selectedProjectIds, selectionMode, bulkDeleting, err, load, canDeleteProject, projectDeleteBlockedReason, projectHasQueuedJob } = options
  const router = useRouter()

  const deletingProjectId = ref<number | null>(null)

  function isProjectMissingError(error: unknown) {
    const message = String((error as any)?.message ?? error ?? '').trim()
    return message === '请求的资源不存在' || message.includes('项目不存在')
  }

  function redirectIfViewingDeletedProject(projectId: number) {
    const route = router.currentRoute.value
    if (!['mixProject', 'aiProject', 'networkProject'].includes(String(route.name || ''))) return
    if (Number(route.params.id || 0) !== Number(projectId)) return
    void router.replace({ path: '/recent', query: { deleted: String(projectId) } })
  }

  async function deleteProject(project: Project) {
    if (bulkDeleting.value) return
    const blocked = projectDeleteBlockedReason(project)
    if (blocked) {
      ElMessage.warning(blocked)
      return
    }
    try {
      const queued = projectHasQueuedJob(project)
      await ElMessageBox.confirm(
        `确定彻底删除项目《${project.title}》？\n\n${queued ? '该项目有排队中的任务，删除时会先取消排队任务。\n\n' : ''}这会同时删除：\n- 项目记录与镜头\n- 相关执行记录\n- 项目素材绑定\n- exports/project_${project.id} 等项目输出目录\n\n该操作无法恢复。`,
        '删除确认',
        { type: 'warning' }
      )
    } catch {
      return
    }
    deletingProjectId.value = project.id
    err.value = ''
    try {
      await api.deleteProject(project.id)
      selectedProjectIds.value = selectedProjectIds.value.filter((id) => id !== project.id)
      await load()
      redirectIfViewingDeletedProject(project.id)
      ElMessage.success(`已删除项目《${project.title}》。`)
    } catch (e: any) {
      if (isProjectMissingError(e)) {
        selectedProjectIds.value = selectedProjectIds.value.filter((id) => id !== project.id)
        await load()
        redirectIfViewingDeletedProject(project.id)
        ElMessage.info(`项目《${project.title}》已不存在，列表已刷新。`)
        return
      }
      ElMessage.error(e?.message ?? String(e))
    } finally {
      deletingProjectId.value = null
    }
  }

  async function deleteSelectedProjects() {
    const targets = visibleProjects.value.filter((project) => selectedProjectIds.value.includes(project.id) && canDeleteProject(project))
    if (!targets.length) {
      ElMessage.info('先选中要删除的项目。')
      return
    }
    const preview = targets.slice(0, 5).map((project) => `- ${project.title}`).join('\n')
    const extra = targets.length > 5 ? `\n... 以及另外 ${targets.length - 5} 个项目` : ''
    const queuedCount = targets.filter((project) => projectHasQueuedJob(project)).length
    try {
      await ElMessageBox.confirm(
        `确定批量删除 ${targets.length} 个项目？\n\n${preview}${extra}\n\n${queuedCount ? `其中 ${queuedCount} 个项目有排队中的任务，删除时会先取消排队任务。\n\n` : ''}这会同时删除项目记录、镜头、执行记录和项目输出目录。\n该操作无法恢复。`,
        '批量删除确认',
        { type: 'warning' }
      )
    } catch {
      return
    }

    bulkDeleting.value = true
    err.value = ''
    const failedIds: number[] = []
    const failedMsgs: string[] = []
    let deletedCount = 0
    try {
      for (const project of targets) {
        try {
          await api.deleteProject(project.id)
          redirectIfViewingDeletedProject(project.id)
          deletedCount += 1
        } catch (e: any) {
          if (isProjectMissingError(e)) {
            redirectIfViewingDeletedProject(project.id)
            deletedCount += 1
            continue
          }
          failedIds.push(project.id)
          failedMsgs.push(`${project.title}：${e?.message ?? String(e)}`)
        }
      }
      await load()
      selectedProjectIds.value = failedIds
      selectionMode.value = failedIds.length > 0
      if (deletedCount > 0 && failedMsgs.length === 0) ElMessage.success(`已批量删除 ${deletedCount} 个项目。`)
      else if (deletedCount > 0 || failedMsgs.length > 0) ElMessage.warning(`已删除 ${deletedCount} 个项目，失败 ${failedMsgs.length} 个。`)
      if (failedMsgs.length) err.value = failedMsgs.slice(0, 3).join('\n')
    } finally {
      bulkDeleting.value = false
    }
  }

  return {
    deletingProjectId,
    deleteProject,
    deleteSelectedProjects,
  }
}
