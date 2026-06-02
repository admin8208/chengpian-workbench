import { onMounted, proxyRefs, ref } from 'vue'
import type { Router } from 'vue-router'
import { api, DEFAULT_CHANNEL_PACKS, type ChannelPack } from '../../../api'

function withTimeout<T>(promise: Promise<T>, ms: number, message: string): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const timer = window.setTimeout(() => reject(new Error(message)), ms)
    promise
      .then((v) => {
        window.clearTimeout(timer)
        resolve(v)
      })
      .catch((e) => {
        window.clearTimeout(timer)
        reject(e)
      })
  })
}

export function useCreatorBaseForm(options: {
  router: Router
  materialMode: 'ai' | 'network'
  heroTitle: string
  modeLabel: string
  modeHint: string
  createButtonLabel: string
}) {
  const { router, materialMode, heroTitle, modeLabel, modeHint, createButtonLabel } = options

  const packs = ref<ChannelPack[]>([])
  const loading = ref(false)
  const creating = ref(false)
  const err = ref('')
  const info = ref('')
  const title = ref('')
  const selectedPack = ref('emotion')
  const source = ref('')
  const inputMode = ref<'text' | 'audio'>('text')
  const mediaPickMode = ref<'smart' | 'random_video'>('smart')
  const audioFile = ref<File | null>(null)

  async function load() {
    loading.value = true
    err.value = ''
    const loadTimer = globalThis.setTimeout(() => {
      loading.value = false
      if (!err.value) err.value = '页面加载超时，请刷新后重试'
    }, 18000)
    try {
      const packsRes = await withTimeout(api.listChannelPacks(), 12000, '频道包加载超时，请稍后重试')
      packs.value = Array.isArray(packsRes) && packsRes.length ? packsRes : [...DEFAULT_CHANNEL_PACKS]
    } catch {
      const fallbackRows = await api.listChannelPacks().catch(() => [])
      packs.value = Array.isArray(fallbackRows) && fallbackRows.length ? fallbackRows : [...DEFAULT_CHANNEL_PACKS]
      info.value = '频道包服务不稳定，已自动切换到本地默认频道包。'
    } finally {
      globalThis.clearTimeout(loadTimer)
      if (!packs.value.length) {
        packs.value = [...DEFAULT_CHANNEL_PACKS]
        if (!info.value) info.value = '频道包为空，已自动恢复为默认四个赛道。'
      }
      const firstPack = packs.value[0]
      if (!packs.value.find((p) => p.key === selectedPack.value) && firstPack) selectedPack.value = firstPack.key
      loading.value = false
    }
  }

  async function createProject() {
    const projectTitle = title.value.trim()
    if (!projectTitle) {
      err.value = '请先输入项目标题。'
      return
    }
    if (creating.value) return
    if (inputMode.value === 'audio' && !audioFile.value) {
      err.value = '音频驱动项目需要先上传音频。'
      return
    }
    creating.value = true
    err.value = ''
    info.value = ''
    try {
      const project = await api.createProject({
        title: projectTitle,
        channel_key: selectedPack.value,
        source_text: inputMode.value === 'text' ? source.value.trim() : '',
        render_config: {
          material_mode: materialMode,
          input_mode: inputMode.value,
          media_pick_mode: materialMode === 'network' ? mediaPickMode.value : 'smart',
        },
      })
      if (inputMode.value === 'audio' && audioFile.value) {
        const asset = await api.uploadProjectAsset(project.id, audioFile.value, 'audio', 'project_source')
        await api.patchProject(project.id, { voice_asset_id: asset.id })
      }
      title.value = ''
      source.value = ''
      audioFile.value = null
      const inputLabel = inputMode.value === 'audio' ? '音频驱动' : '文案驱动'
      const pickLabel = materialMode === 'network' && mediaPickMode.value === 'random_video' ? ' + 随机视频' : ''
      info.value = `已创建项目《${project.title}》，当前使用${inputLabel} + ${modeLabel}${pickLabel}模式。进入项目页后再开始生成会更稳定。`
      await router.push({ path: materialMode === 'ai' ? `/p/ai/${project.id}` : `/p/network/${project.id}` })
    } catch (e: any) {
      err.value = e?.message ?? String(e)
    } finally {
      creating.value = false
    }
  }

  onMounted(() => {
    void load()
  })

  return proxyRefs({
    packs,
    loading,
    creating,
    err,
    info,
    title,
    selectedPack,
    source,
    inputMode,
    mediaPickMode,
    audioFile,
    heroTitle,
    modeLabel,
    modeHint,
    createButtonLabel,
    createProject,
  })
}
