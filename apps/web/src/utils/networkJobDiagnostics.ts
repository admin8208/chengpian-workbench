import type { Job } from '../api'
import { networkJobDiagnosticsConfig } from './jobDiagnosticsConfig'
import { autopilotFlowSteps, failedStageSummary, mainStageLabel, stageSummary, substageLabel } from './jobDiagnostics'

export function networkSubstageLabel(j: Job) {
  return substageLabel(j, networkJobDiagnosticsConfig)
}

export function networkMainStageLabel(j: Job) {
  return mainStageLabel(j)
}

export function networkStageSummary(j: Job) {
  return stageSummary(j, networkJobDiagnosticsConfig)
}

export function networkFailedStageSummary(j: Job) {
  return failedStageSummary(j, networkJobDiagnosticsConfig)
}

export function networkAutopilotFlowSteps(j: Job) {
  return autopilotFlowSteps(j, networkJobDiagnosticsConfig)
}
