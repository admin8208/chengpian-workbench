import { proxyRefs } from 'vue'

import { aiProjectPlugin } from './aiProjectPlugin'
import { useProjectViewCore } from '../core/useProjectViewCore'


export function useAiProjectView() {
  return proxyRefs(useProjectViewCore({ plugin: aiProjectPlugin }))
}
