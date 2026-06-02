import type { Job } from '../../../api'

export type ProjectFlowActions = {
  continueAutopilot: () => Promise<void>
  startAutofill: () => Promise<void>
  startImages: () => Promise<void>
  startRender: () => Promise<void>
  focusSceneIssues: () => void
}

export type ProjectDiagnosticsProvider = {
  substageLabel: (job: Job) => string
  mainStageLabel: (job: Job) => string
  stageSummary: (job: Job) => string
  failedStageSummary: (job: Job) => string
  flowSteps: (job: Job) => any[]
}

export type ProjectRunActions = {
  confirmScriptAndRunAutopilot: (script?: string) => Promise<void>
  runAutopilot: () => Promise<void>
  continueAutopilot: () => Promise<void>
  rerunAutopilot: () => Promise<void>
  startAutofill: () => Promise<void>
  startImages: () => Promise<void>
  startSelectedSceneImage: () => Promise<void>
  startRender: () => Promise<void>
}

export type ProjectActionAdapter = ProjectFlowActions & {
  startStoryboardPrimaryAction: () => Promise<void>
  startScenePrimaryAction: () => Promise<void>
}

export type ProjectActionAdapterOptions = {
  runActions: ProjectRunActions
  focusSceneIssues: () => void
}

export type ProjectUiLabels = {
  modeName: string
  storyboardStepLabel: string
  storyboardStepDesc: string
  storyboardStepTips: string
  storyboardIssueLabel: string
  storyboardReadyLabel: string
  storyboardScenePanelDesc: string
  storyboardMissingLabel: string
  storyboardDuplicateLabel: string
  storyboardModeTone: 'ok' | 'run'
  storyboardPrimaryActionLabel: string | null
}

export type ProjectViewPlugin = {
  useFlow: (args: any) => any
  useSceneWorkspace: (args: any) => any
  diagnosticsProvider: ProjectDiagnosticsProvider
  createActionAdapter: (options: ProjectActionAdapterOptions) => ProjectActionAdapter
  uiLabels: ProjectUiLabels
}

async function noopAsync() {}

export function createNoopProjectActionAdapter(): ProjectActionAdapter {
  return {
    continueAutopilot: noopAsync,
    startAutofill: noopAsync,
    startImages: noopAsync,
    startRender: noopAsync,
    focusSceneIssues: () => {},
    startStoryboardPrimaryAction: noopAsync,
    startScenePrimaryAction: noopAsync,
  }
}
