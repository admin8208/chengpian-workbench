import type { Job } from '../api'
import { aiJobDiagnosticsConfig } from './jobDiagnosticsConfig'
import { autopilotFlowSteps, failedStageSummary, mainStageLabel, stageSummary, substageLabel } from './jobDiagnostics'

export function aiSubstageLabel(j: Job) {
  return substageLabel(j, aiJobDiagnosticsConfig)
}

export function aiMainStageLabel(j: Job) {
  return mainStageLabel(j)
}

export function aiStageSummary(j: Job) {
  return stageSummary(j, aiJobDiagnosticsConfig)
}

export function aiFailedStageSummary(j: Job) {
  return failedStageSummary(j, aiJobDiagnosticsConfig)
}

export function aiAutopilotFlowSteps(j: Job) {
  return autopilotFlowSteps(j, aiJobDiagnosticsConfig)
}
