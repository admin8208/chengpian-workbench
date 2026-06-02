import { computed, ref, watch, type Ref } from 'vue'
import type { Asset } from '../../../api'

type FinalStatus = { exists: boolean; url: string; size: number } | null

type UseProjectVideoOutputsArgs = {
  projectAssets: Ref<Asset[]>
}

export function useProjectVideoOutputs(args: UseProjectVideoOutputsArgs) {
  const exportVideos = computed(() => args.projectAssets.value.filter((a) => a.kind === 'video' && (a.tag || '') === 'export'))
  const selectedVideoUrl = ref('')
  const selectedVideoAsset = computed(() => {
    const selectedUrl = String(selectedVideoUrl.value || '').trim()
    if (!selectedUrl) return null
    const direct = args.projectAssets.value.find((a) => String(a.url || '').trim() === selectedUrl)
    if (direct) return direct
    if (finalStatus.value?.exists && selectedUrl === String(finalStatus.value.url || '').trim()) {
      return exportVideos.value[0] || null
    }
    return null
  })
  const userSelectedVideo = ref(false)
  const finalStatus = ref<FinalStatus>(null)
  let settingVideo = false

  watch(
    () => selectedVideoUrl.value,
    () => {
      if (!settingVideo) userSelectedVideo.value = true
    }
  )

  function resetVideoOutputState() {
    finalStatus.value = null
    selectedVideoUrl.value = ''
    userSelectedVideo.value = false
  }

  function applyAutoSelectedVideo() {
    settingVideo = true
    userSelectedVideo.value = false
    selectedVideoUrl.value = ''
    if (finalStatus.value?.exists) selectedVideoUrl.value = finalStatus.value.url
    else if (exportVideos.value.length) selectedVideoUrl.value = exportVideos.value[0]!.url
    settingVideo = false
  }

  function preserveSelectionAfterAssetsRefresh() {
    const selectedStillExists = !!args.projectAssets.value.find((a) => a.url === selectedVideoUrl.value)
    const selectedMatchesFinal = Boolean(selectedVideoUrl.value && finalStatus.value?.exists && selectedVideoUrl.value === finalStatus.value.url)
    if (selectedVideoUrl.value && !selectedStillExists && !selectedMatchesFinal) {
      userSelectedVideo.value = false
      applyAutoSelectedVideo()
      return
    }
    if (!userSelectedVideo.value && !selectedVideoUrl.value) {
      applyAutoSelectedVideo()
    }
  }

  return {
    exportVideos,
    selectedVideoUrl,
    selectedVideoAsset,
    userSelectedVideo,
    finalStatus,
    resetVideoOutputState,
    applyAutoSelectedVideo,
    preserveSelectionAfterAssetsRefresh,
  }
}
