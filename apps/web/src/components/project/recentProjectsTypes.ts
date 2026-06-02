import type { Project, ProjectCenterItem, ProjectFeedJob } from '../../api'

export type ProjectTone = '' | 'success' | 'warning' | 'danger'

export type ProjectTagView = {
  label: string
  type: 'info' | 'warning' | 'danger' | 'success'
}

export type ProjectCardView = {
  project: Project
  tone: ProjectTone
  statusLabel: string
  stageText: string
  actionLabel: string
  actionKey: 'open_project' | 'continue_project' | 'rerun_project'
  notice: string
  tags: ProjectTagView[]
  updatedAtText: string
  finalExists: boolean
  emphasizeAssetIssues: boolean
  missingAssetLabel: string
  missingAssetCount: number
  duplicateAssetCount: number
  materialModeLabel: string
  continueStageLabel: string
  chainAttemptsLabel: string
  currentJob: ProjectFeedJob | null
  currentJobIsActive: boolean
  currentJobKindLabel: string
  currentJobStageLabel: string
  currentJobSubstageLabel: string
  currentJobStageSummary: string
  currentJobStatusLabel: string
  currentJobProgress: number
  currentJobMessage: string
  currentJobHint: string
  currentJobUpdatedAtText: string
  currentJobResumeLabel: string
  needsLlmSettings: boolean
  needsMediaSettings: boolean
  needsTtsSettings: boolean
  canDelete: boolean
  selected: boolean
}

export type ProjectFeedCardSource = ProjectCenterItem
