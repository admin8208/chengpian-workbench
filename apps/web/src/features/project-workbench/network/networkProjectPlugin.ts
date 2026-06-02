import { createNetworkProjectActionAdapter } from '../plugins/projectActionAdapters'
import { networkProjectDiagnosticsProvider } from '../plugins/projectDiagnosticsProviders'
import type { ProjectViewPlugin } from '../plugins/projectViewPlugin'

import { useNetworkProjectFlow } from './useNetworkProjectFlow'
import { useNetworkProjectSceneWorkspace } from './useNetworkProjectSceneWorkspace'

export const networkProjectPlugin: ProjectViewPlugin = {
  useFlow: useNetworkProjectFlow,
  useSceneWorkspace: useNetworkProjectSceneWorkspace,
  diagnosticsProvider: networkProjectDiagnosticsProvider,
  createActionAdapter: createNetworkProjectActionAdapter,
  uiLabels: {
    modeName: '网络素材模式',
    storyboardStepLabel: '素材匹配',
    storyboardStepDesc: '镜头结构、检索与素材绑定',
    storyboardStepTips: '系统会根据已确认的文案或转写结果生成镜头结构，再自动搜索、导入并绑定素材。',
    storyboardIssueLabel: '素材',
    storyboardReadyLabel: '素材已就绪',
    storyboardScenePanelDesc: '先修缺素材和重复素材，再去看最终成片。',
    storyboardMissingLabel: '缺素材',
    storyboardDuplicateLabel: '重复素材',
    storyboardModeTone: 'run',
    storyboardPrimaryActionLabel: null,
  },
}
