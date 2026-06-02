import { computed, ref, type Ref } from 'vue'
import type { ProjectDetail, Scene } from '../../../api'

export function useMixProjectSceneSelection(options: {
  project: Ref<ProjectDetail | null>
}) {
  const { project } = options

  const selectedSceneId = ref<number | null>(null)
  const selectedScene = computed(() => (project.value?.scenes || []).find((scene) => scene.id === selectedSceneId.value) ?? null)

  function patchSceneLocal(nextScene: Scene) {
    if (!project.value) return
    const scenes = Array.isArray(project.value.scenes) ? [...project.value.scenes] : []
    const idx = scenes.findIndex((scene) => scene.id === nextScene.id)
    if (idx < 0) return
    scenes[idx] = nextScene
    project.value = { ...project.value, scenes }
  }

  function ensureSelectedScene(nextProject: ProjectDetail | null | undefined) {
    const scenes = nextProject?.scenes || []
    if (!scenes.length) {
      selectedSceneId.value = null
      return
    }
    if (!selectedSceneId.value || !scenes.some((scene) => scene.id === selectedSceneId.value)) {
      selectedSceneId.value = scenes[0]!.id
    }
  }

  function resetSelectedScene() {
    selectedSceneId.value = null
  }

  return {
    selectedSceneId,
    selectedScene,
    patchSceneLocal,
    ensureSelectedScene,
    resetSelectedScene,
  }
}
