import { aiAutopilotFlowSteps, aiFailedStageSummary, aiMainStageLabel, aiStageSummary, aiSubstageLabel } from '../../../utils/aiJobDiagnostics'
import { networkAutopilotFlowSteps, networkFailedStageSummary, networkMainStageLabel, networkStageSummary, networkSubstageLabel } from '../../../utils/networkJobDiagnostics'
import type { ProjectDiagnosticsProvider } from './projectViewPlugin'

export const aiProjectDiagnosticsProvider: ProjectDiagnosticsProvider = {
  substageLabel: aiSubstageLabel,
  mainStageLabel: aiMainStageLabel,
  stageSummary: aiStageSummary,
  failedStageSummary: aiFailedStageSummary,
  flowSteps: aiAutopilotFlowSteps,
}

export const networkProjectDiagnosticsProvider: ProjectDiagnosticsProvider = {
  substageLabel: networkSubstageLabel,
  mainStageLabel: networkMainStageLabel,
  stageSummary: networkStageSummary,
  failedStageSummary: networkFailedStageSummary,
  flowSteps: networkAutopilotFlowSteps,
}
