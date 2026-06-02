import { computed, ref, type ComputedRef } from 'vue'
import type { Project } from '../../api'

export function useRecentProjectsSelection(options: {
  visibleProjects: ComputedRef<Project[]>
  bulkDeleting: { value: boolean }
  canDeleteProject: (project: Project) => boolean
}) {
  const { visibleProjects, bulkDeleting, canDeleteProject } = options
  const selectionMode = ref(false)
  const selectedProjectIds = ref<number[]>([])

  function isSelectedProject(projectId: number) {
    return selectedProjectIds.value.includes(projectId)
  }

  function setSelectionMode(next: boolean) {
    selectionMode.value = next
    if (!next) selectedProjectIds.value = []
  }

  function toggleProjectSelection(project: Project) {
    if (!canDeleteProject(project) || bulkDeleting.value) return
    if (isSelectedProject(project.id)) selectedProjectIds.value = selectedProjectIds.value.filter((id) => id !== project.id)
    else selectedProjectIds.value = [...selectedProjectIds.value, project.id]
  }

  const deletableVisibleProjects = computed(() => visibleProjects.value.filter((p) => canDeleteProject(p)))
  const allDeletableVisibleSelected = computed(() => deletableVisibleProjects.value.length > 0 && deletableVisibleProjects.value.every((p) => selectedProjectIds.value.includes(p.id)))

  function selectAllVisibleProjects() {
    selectedProjectIds.value = deletableVisibleProjects.value.map((p) => p.id)
  }

  function clearSelectedProjects() {
    selectedProjectIds.value = []
  }

  function keepSelectionInProjects(projects: Project[]) {
    selectedProjectIds.value = selectedProjectIds.value.filter((id) => projects.some((p) => p.id === id))
  }

  return {
    selectionMode,
    selectedProjectIds,
    isSelectedProject,
    setSelectionMode,
    toggleProjectSelection,
    deletableVisibleProjects,
    allDeletableVisibleSelected,
    selectAllVisibleProjects,
    clearSelectedProjects,
    keepSelectionInProjects,
  }
}
