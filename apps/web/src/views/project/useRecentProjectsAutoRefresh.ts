import { onMounted, onUnmounted, ref, type Ref } from 'vue'

const AUTO_REFRESH_INTERVAL = 30000

export function useRecentProjectsAutoRefresh(options: {
  pageLoading: Ref<boolean>
  jobActionBusy: Ref<boolean>
  retryLoad: () => void
}) {
  const { pageLoading, jobActionBusy, retryLoad } = options
  const autoRefreshTimer = ref<ReturnType<typeof setInterval> | null>(null)

  function startAutoRefresh() {
    stopAutoRefresh()
    autoRefreshTimer.value = setInterval(() => {
      if (!pageLoading.value && !jobActionBusy.value) retryLoad()
    }, AUTO_REFRESH_INTERVAL)
  }

  function stopAutoRefresh() {
    if (autoRefreshTimer.value) {
      clearInterval(autoRefreshTimer.value)
      autoRefreshTimer.value = null
    }
  }

  onMounted(() => {
    retryLoad()
    startAutoRefresh()
  })

  onUnmounted(() => {
    stopAutoRefresh()
  })

  return {
    startAutoRefresh,
    stopAutoRefresh,
  }
}
