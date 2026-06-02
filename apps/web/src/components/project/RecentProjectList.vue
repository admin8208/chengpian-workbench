<script setup lang="ts">
import RecentProjectListItem from './RecentProjectListItem.vue'
import type { ProjectCardView } from './recentProjectsTypes'

defineProps<{
  cards: ProjectCardView[]
  selectionMode: boolean
  bulkDeleting: boolean
  deletingProjectId: number | null
}>()

const emit = defineEmits<{
  openProject: [projectId: number]
  openFinal: [projectId: number]
  goSettings: [tab: 'llm' | 'media' | 'tts']
  toggleSelect: [projectId: number]
  deleteProject: [projectId: number]
}>()
</script>

<template>
  <div class="project-list">
    <RecentProjectListItem
      v-for="card in cards"
      :key="card.project.id"
      :card="card"
      :selection-mode="selectionMode"
      :bulk-deleting="bulkDeleting"
      :deleting-project-id="deletingProjectId"
      @open-project="emit('openProject', $event)"
      @open-final="emit('openFinal', $event)"
      @go-settings="emit('goSettings', $event)"
      @toggle-select="emit('toggleSelect', $event)"
      @delete-project="emit('deleteProject', $event)"
    />
  </div>
</template>

<style scoped>
.project-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
</style>
