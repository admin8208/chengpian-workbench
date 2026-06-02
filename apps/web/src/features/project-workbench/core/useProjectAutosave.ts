import { ref, watch, type Ref } from 'vue'
import { api, type ProjectDetail } from '../../../api'

export function useProjectAutosave(options: {
  projectId: Ref<number | null>
  project: Ref<ProjectDetail | null>
}) {
  const { projectId, project } = options
  const saveErr = ref('')
  const autosaving = ref(false)
  const titleInput = ref('')
  const sourceInput = ref('')
  let hydratingInputs = false
  let saveTitleTimer: number | null = null
  let saveSourceTimer: number | null = null

  function hydrateProjectInputs() {
    hydratingInputs = true
    titleInput.value = project.value?.title || ''
    sourceInput.value = project.value?.source_text || ''
    hydratingInputs = false
  }

  async function autosaveTitleNow() {
    const id = projectId.value
    const t = titleInput.value.trim()
    if (!id || !project.value || !t) return
    if (t === (project.value.title || '').trim()) return
    autosaving.value = true
    saveErr.value = ''
    try {
      await api.patchProject(id, { title: t })
      project.value.title = t
    } catch {
      saveErr.value = '标题保存失败：请检查网络或稍后重试。'
    } finally {
      autosaving.value = false
    }
  }

  async function autosaveSourceNow() {
    const id = projectId.value
    if (!id || !project.value) return
    const v = sourceInput.value
    if (v === (project.value.source_text || '')) return
    autosaving.value = true
    saveErr.value = ''
    try {
      await api.patchProject(id, { source_text: v })
      project.value.source_text = v
    } catch {
      saveErr.value = '原文/要点保存失败：请检查网络或稍后重试。'
    } finally {
      autosaving.value = false
    }
  }

  watch(() => titleInput.value, () => {
    if (hydratingInputs) return
    if (saveTitleTimer) window.clearTimeout(saveTitleTimer)
    saveTitleTimer = window.setTimeout(() => {
      void autosaveTitleNow()
    }, 600)
  })

  watch(() => sourceInput.value, () => {
    if (hydratingInputs) return
    if (saveSourceTimer) window.clearTimeout(saveSourceTimer)
    saveSourceTimer = window.setTimeout(() => {
      void autosaveSourceNow()
    }, 700)
  })

  function clearAutosaveTimers() {
    if (saveTitleTimer) window.clearTimeout(saveTitleTimer)
    if (saveSourceTimer) window.clearTimeout(saveSourceTimer)
  }

  return {
    saveErr,
    autosaving,
    titleInput,
    sourceInput,
    hydrateProjectInputs,
    clearAutosaveTimers,
  }
}
