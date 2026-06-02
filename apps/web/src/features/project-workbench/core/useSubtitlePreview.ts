import { ref, watch, type Ref } from 'vue'

export function useSubtitlePreview(subtitleUrl: Ref<string | null | undefined>) {
  const subtitlePreviewText = ref('')
  const subtitlePreviewBusy = ref(false)
  const subtitlePreviewErr = ref('')

  function summarizeSubtitleText(raw: string) {
    const lines = String(raw || '')
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter((line) => line && !/^\d+$/.test(line) && !/^\d{2}:\d{2}:\d{2}[,.]\d{3}\s*-->/.test(line))
    return lines.join('\n').trim()
  }

  async function loadSubtitlePreview(url: string | null | undefined) {
    const nextUrl = String(url || '').trim()
    subtitlePreviewText.value = ''
    subtitlePreviewErr.value = ''
    if (!nextUrl) return
    subtitlePreviewBusy.value = true
    try {
      const res = await fetch(nextUrl, { credentials: 'include' })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const txt = await res.text()
      subtitlePreviewText.value = summarizeSubtitleText(txt)
      if (!subtitlePreviewText.value) subtitlePreviewErr.value = '字幕文件已生成，但暂时没有解析出可展示的正文。'
    } catch (e: any) {
      subtitlePreviewErr.value = e?.message ?? '字幕预览加载失败'
    } finally {
      subtitlePreviewBusy.value = false
    }
  }

  watch(
    subtitleUrl,
    (url) => {
      loadSubtitlePreview(url).catch(() => {})
    },
    { immediate: true }
  )

  return {
    subtitlePreviewText,
    subtitlePreviewBusy,
    subtitlePreviewErr,
  }
}
