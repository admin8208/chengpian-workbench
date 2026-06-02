import type { ProjectActionAdapter, ProjectActionAdapterOptions } from './projectViewPlugin'

async function noopAsync() {}

export function createAiProjectActionAdapter(options: ProjectActionAdapterOptions): ProjectActionAdapter {
  const { runActions, focusSceneIssues } = options
  return {
    continueAutopilot: runActions.continueAutopilot,
    startAutofill: noopAsync,
    startImages: runActions.startImages,
    startRender: runActions.startRender,
    focusSceneIssues,
    startStoryboardPrimaryAction: runActions.startImages,
    startScenePrimaryAction: runActions.startSelectedSceneImage,
  }
}

export function createNetworkProjectActionAdapter(options: ProjectActionAdapterOptions): ProjectActionAdapter {
  const { runActions, focusSceneIssues } = options
  return {
    continueAutopilot: runActions.continueAutopilot,
    startAutofill: runActions.startAutofill,
    startImages: noopAsync,
    startRender: runActions.startRender,
    focusSceneIssues,
    startStoryboardPrimaryAction: runActions.startAutofill,
    startScenePrimaryAction: noopAsync,
  }
}
