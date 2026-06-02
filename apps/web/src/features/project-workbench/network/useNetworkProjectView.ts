import { proxyRefs } from 'vue'

import { networkProjectPlugin } from './networkProjectPlugin'
import { useProjectViewCore } from '../core/useProjectViewCore'


export function useNetworkProjectView() {
  return proxyRefs(useProjectViewCore({ plugin: networkProjectPlugin }))
}
