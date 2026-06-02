import { computed, type ComputedRef } from 'vue'
import type { Project } from '../../api'
import type { ProjectCardView, ProjectFeedCardSource } from '../../components/project/recentProjectsTypes'

export function useRecentProjectsViewModel(options: {
  projects: ComputedRef<Project[]>
  feedItems: ComputedRef<ProjectFeedCardSource[]>
  isSelectedProject: (projectId: number) => boolean
}) {
  const { projects, feedItems, isSelectedProject } = options
  const projectMap = computed(() => new Map(projects.value.map((project) => [project.id, project])))

  const projectCards = computed<ProjectCardView[]>(() => feedItems.value.flatMap((item) => {
    const project = projectMap.value.get(item.project_id)
    if (!project) {
      return []
    }
    return [{
      project,
      tone: item.tone,
      statusLabel: item.status_label,
      stageText: item.stage_text,
      actionLabel: item.action_label,
      actionKey: item.action_key,
      notice: item.notice,
      tags: item.tags,
      updatedAtText: item.updated_at_text,
      finalExists: item.final_exists,
      emphasizeAssetIssues: item.emphasize_asset_issues,
      missingAssetLabel: item.missing_asset_label,
      missingAssetCount: item.missing_asset_count,
      duplicateAssetCount: item.duplicate_asset_count,
      materialModeLabel: item.material_mode_label,
      continueStageLabel: item.continue_stage_label,
      chainAttemptsLabel: item.current_job?.chain_attempts_label || '',
      currentJob: item.current_job || null,
      currentJobIsActive: item.current_job_is_active,
      currentJobKindLabel: item.current_job?.kind_label || '',
      currentJobStageLabel: item.current_job?.stage_label || '',
      currentJobSubstageLabel: item.current_job?.substage_label || '',
      currentJobStageSummary: item.current_job?.stage_summary || '',
      currentJobStatusLabel: item.current_job?.status_label || '',
      currentJobProgress: Number(item.current_job?.progress || 0),
      currentJobMessage: item.current_job?.message_label || '',
      currentJobHint: item.current_job?.hint || '',
      currentJobUpdatedAtText: item.current_job?.updated_at_text || '',
      currentJobResumeLabel: item.current_job?.resume_label || '',
      needsLlmSettings: item.needs_llm_settings,
      needsMediaSettings: item.needs_media_settings,
      needsTtsSettings: item.needs_tts_settings,
      canDelete: item.can_delete,
      selected: isSelectedProject(item.project_id),
    }]
  }))

  const runningProjectCount = computed(() => feedItems.value.filter((item) => ['queued', 'running', 'paused'].includes(String(item.status || '').trim().toLowerCase())).length)
  const failedProjectCount = computed(() => feedItems.value.filter((item) => String(item.status || '').trim().toLowerCase() === 'failed').length)
  const finalProjectCount = computed(() => feedItems.value.filter((item) => item.final_exists).length)

  function primaryJob(project: Project) {
    return feedItems.value.find((item) => item.project_id === project.id)?.current_job || null
  }

  function activeJobStatus(project: Project) {
    return feedItems.value.find((item) => item.project_id === project.id)?.status || ''
  }

  return {
    primaryJob,
    activeJobStatus,
    projectCards,
    runningProjectCount,
    failedProjectCount,
    finalProjectCount,
  }
}
