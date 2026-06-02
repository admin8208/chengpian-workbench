import { computed, onMounted, onUnmounted, ref } from 'vue'
import { api, type FeedConnectionState, type Project, type ProjectCenterFeed } from '../../api'
import { formatTime } from '../../utils/dateTime'

const PROJECT_CENTER_LIMIT = 50
const FALLBACK_POLL_INTERVAL = 15000

export function useRecentProjectsData() {
  const feed = ref<ProjectCenterFeed | null>(null)
  const err = ref('')
  const pageLoading = ref(true)
  const lastUpdateTime = ref('')
  const runtimeWarning = ref('')
  const projectionRebuilding = ref(false)
  const feedConnectionState = ref<FeedConnectionState>('connecting')
  let pollTimer: ReturnType<typeof setInterval> | null = null

  const projects = computed<Project[]>(() => {
    const items = feed.value?.items || []
    return items.map((item) => ({
      id: item.project_id,
      title: item.title,
      workflow: item.workflow,
      channel_key: item.channel_key,
      status: item.status,
      script: '',
      script_source: '',
      source_text: '',
      character_profile: '',
      publish_title: '',
      publish_hashtags: '',
      render_config: { material_mode: item.material_mode },
      created_at: item.updated_at,
      updated_at: item.updated_at,
    }))
  })

  const visibleProjects = computed(() => projects.value)
  let loadPromise: Promise<void> | null = null

  async function load() {
    if (loadPromise) return loadPromise
    err.value = ''
    pageLoading.value = true
    loadPromise = (async () => {
      try {
        feed.value = await api.getProjectCenterFeed(PROJECT_CENTER_LIMIT)
        projectionRebuilding.value = Boolean(feed.value?.rebuilding)
        runtimeWarning.value = ''
      } catch (e: any) {
        err.value = e?.message ?? String(e)
      } finally {
        pageLoading.value = false
        lastUpdateTime.value = formatTime(new Date())
        loadPromise = null
      }
    })()
    return loadPromise
  }

  function retryLoad() {
    load().catch((e) => {
      err.value = e?.message ?? String(e)
    })
  }

  function stopFallbackPolling() {
    if (pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
  }

  function startFallbackPolling() {
    if (pollTimer) return
    pollTimer = setInterval(() => {
      if (!pageLoading.value) retryLoad()
    }, FALLBACK_POLL_INTERVAL)
  }

  onMounted(() => {
    unsubscribeFeedEvents = api.subscribeFeedEvents({
      onFeed: (payload) => {
        const projectIds = Array.isArray(payload?.project_ids) ? payload.project_ids.map((id: any) => Number(id)).filter((id: number) => Number.isFinite(id) && id > 0) : []
        if (!projectIds.length) return
        if (projects.value.some((project) => projectIds.includes(project.id))) {
          retryLoad()
        }
      },
      onOpen: () => {
        stopFallbackPolling()
        runtimeWarning.value = ''
      },
      onError: () => {
        runtimeWarning.value = '项目中心实时连接已中断，系统正在自动重连；当前会临时降级为轮询刷新。'
      },
      onStateChange: (state) => {
        feedConnectionState.value = state
        if (state === 'open') {
          stopFallbackPolling()
          runtimeWarning.value = ''
          return
        }
        if (state === 'polling') {
          startFallbackPolling()
          runtimeWarning.value = '项目中心实时连接暂未恢复，当前已降级为轮询刷新。'
        }
      },
    })
  })

  onUnmounted(() => {
    stopFallbackPolling()
    unsubscribeFeedEvents?.()
    unsubscribeFeedEvents = null
  })

  return {
    feed,
    projects,
    packs: ref([]),
    runtimes: ref({}),
    jobs: ref([]),
    err,
    runtimeWarning,
    projectionRebuilding,
    feedConnectionState,
    pageLoading,
    lastUpdateTime,
    visibleProjects,
    load,
    retryLoad,
  }
}
let unsubscribeFeedEvents: null | (() => void) = null
