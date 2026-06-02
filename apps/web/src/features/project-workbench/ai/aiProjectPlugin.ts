import { createAiProjectActionAdapter } from '../plugins/projectActionAdapters'
import { aiProjectDiagnosticsProvider } from '../plugins/projectDiagnosticsProviders'
import type { ProjectViewPlugin } from '../plugins/projectViewPlugin'

import { useAiProjectFlow } from './useAiProjectFlow'
import { useAiProjectSceneWorkspace } from './useAiProjectSceneWorkspace'

export const aiProjectPlugin: ProjectViewPlugin = {
  useFlow: useAiProjectFlow,
  useSceneWorkspace: useAiProjectSceneWorkspace,
  diagnosticsProvider: aiProjectDiagnosticsProvider,
  createActionAdapter: createAiProjectActionAdapter,
  uiLabels: {
    modeName: '智能生图链路模式',
    storyboardStepLabel: '智能出图',
    storyboardStepDesc: '镜头结构、提示词与出图',
    storyboardStepTips: '系统会根据已确认的文案或转写结果生成镜头结构，再按镜头提示词自动补足构图、光线、连续性与画质增强后生成画面。',
    storyboardIssueLabel: '画面',
    storyboardReadyLabel: '出图已就绪',
    storyboardScenePanelDesc: '先修缺镜头图和重复素材；最终成片会自动加入轻微运镜与更自然的镜头转场。',
    storyboardMissingLabel: '缺镜头图',
    storyboardDuplicateLabel: '重复素材',
    storyboardModeTone: 'ok',
    storyboardPrimaryActionLabel: '批量生成全部镜头',
  },
}
