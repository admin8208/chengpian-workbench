import { onMounted, proxyRefs, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useSettingsLlm } from './llm/useSettingsLlm'
import { useSettingsImage } from './image/useSettingsImage'
import { useSettingsMedia } from './media/useSettingsMedia'
import { useSettingsTts } from './tts/useSettingsTts'
import { useSettingsAccounts } from './account/useSettingsAccounts'

export type SettingsTab = 'llm' | 'image' | 'media' | 'tts' | 'account'
type SetupState = 'loading' | 'ready' | 'missing'

export function useSettingsView() {
  const route = useRoute()
  const router = useRouter()

  const tab = ref<SettingsTab>('llm')
  const busy = ref(false)
  const info = ref('')
  const err = ref('')
  const media = useSettingsMedia({ err, info })
  const accounts = useSettingsAccounts({ err, info })

  const showPlainSecrets = ref(false)

  const llm = useSettingsLlm({ err, info })
  const image = useSettingsImage({ err, info })

  const tts = useSettingsTts({ err, info, busy })

  function setTab(next: SettingsTab) {
    tab.value = next
    router.replace({ query: { ...route.query, tab: next } })
  }

  function applyTabFromQuery() {
    const next = String(route.query.tab || '').trim().toLowerCase()
    if (next === 'llm' || next === 'image' || next === 'media' || next === 'tts' || next === 'account') tab.value = next
    if (!isAdmin.value && tab.value === 'account') tab.value = 'llm'
  }

  watch(() => route.query.tab, applyTabFromQuery)

  function setupStateLabel(state: SetupState) {
    if (state === 'loading') return '检测中'
    if (state === 'ready') return '已配置'
    return '待补'
  }

  const llmSetupState = llm.llmSetupState
  const imageSetupState = image.imageSetupState
  const mediaSetupState = media.mediaSetupState
  const ttsSetupState = tts.ttsSetupState

  const isAdmin = accounts.isAdmin

  function hydrateForms() {
    llm.hydrateLlmForm()
    image.hydrateImageForm()
    media.hydrateMediaForm()
    tts.hydrateTtsForm()
  }

  async function loadAll() {
    err.value = ''
    const failures: string[] = []
    await Promise.all([
      accounts.loadAccounts(failures),
      llm.loadLlm(failures),
      image.loadImage(failures),
      media.loadMedia(failures),
      tts.loadTts(failures),
    ])
    hydrateForms()
    applyTabFromQuery()
    if (failures.length) err.value = failures.join('；')
  }

  const saveLlm = () => llm.saveLlm(loadAll)
  const testLlm = () => llm.testLlm()
  const saveImage = () => image.saveImage(loadAll)
  const testImage = () => image.testImage()
  const llmPanelModel = proxyRefs({
    ...llm,
    saveLlm,
    testLlm,
  })
  const imagePanelModel = proxyRefs({
    ...image,
    saveImage,
    testImage,
  })

  const saveMediaKey = (provider: 'pexels' | 'pixabay', key: string) => media.saveMediaKey(provider, key, loadAll)
  const runMediaTest = () => media.runMediaTest()
  const mediaPanelModel = proxyRefs({
    ...media,
    saveMediaKey,
    runMediaTest,
  })
  const saveTtsBackend = () => tts.saveTtsBackend()
  const reloadTtsStatus = () => tts.reloadTtsStatus()
  const previewCurrentTts = (mode?: 'offline_piper' | 'edge') => tts.previewCurrentTts(mode)
  const installOfflineTts = () => tts.installOfflineTts()
  const cleanupIncompatibleVoices = () => tts.cleanupIncompatibleVoices()
  const ttsPanelModel = proxyRefs({
    ...tts,
    saveTtsBackend,
    reloadTtsStatus,
    previewCurrentTts,
    installOfflineTts,
    cleanupIncompatibleVoices,
  })
  const createSubAccount = () => accounts.createSubAccount()
  const toggleSubAccount = (user: any, enabled: boolean) => accounts.toggleSubAccount(user, enabled)
  const resetSubAccountPassword = (user: any) => accounts.resetSubAccountPassword(user)
  const accountsPanelModel = proxyRefs({
    ...accounts,
    createSubAccount,
    toggleSubAccount,
    resetSubAccountPassword,
  })

  onMounted(async () => {
    applyTabFromQuery()
    await loadAll().catch((e: any) => {
      err.value = e?.message ?? String(e)
    })
  })

  return {
    router,
    tab,
    busy,
    info,
    err,
    showPlainSecrets,
    llm: llmPanelModel,
    image: imagePanelModel,
    accounts: accountsPanelModel,
    authStatus: accounts.authStatus,
    isAdmin,
    media: mediaPanelModel,
    tts: ttsPanelModel,
    llmSetupState,
    imageSetupState,
    mediaSetupState,
    ttsSetupState,
    setTab,
    setupStateLabel,
  }
}
