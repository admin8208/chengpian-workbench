<script setup lang="ts">
import { ElButton } from 'element-plus'

defineProps<{
  selectionMode: boolean
  selectedCount: number
  bulkDeleting: boolean
  deletableVisibleCount: number
  allDeletableVisibleSelected: boolean
}>()

const emit = defineEmits<{
  toggleSelectionMode: []
  toggleSelectAll: []
  deleteSelected: []
}>()
</script>

<template>
  <div class="list-toolbar">
    <div class="muted toolbar-note">
      {{ selectionMode ? `已选 ${selectedCount} 个项目，仅可删除未执行中的项目。` : '项目列表' }}
    </div>
    <div class="toolbar-actions">
      <ElButton :disabled="bulkDeleting" @click="emit('toggleSelectionMode')">{{ selectionMode ? '取消选择' : '批量选择' }}</ElButton>
      <ElButton v-if="selectionMode" :disabled="bulkDeleting || !deletableVisibleCount" @click="emit('toggleSelectAll')">
        {{ allDeletableVisibleSelected ? '清空已选' : '全选可删除' }}
      </ElButton>
      <ElButton v-if="selectionMode" type="danger" :disabled="bulkDeleting || !selectedCount" :loading="bulkDeleting" @click="emit('deleteSelected')">
        批量删除项目
      </ElButton>
    </div>
  </div>
</template>

<style scoped>
.list-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}

.toolbar-note {
  line-height: 1.5;
}

.toolbar-actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  align-items: center;
}

@media (max-width: 768px) {
  .toolbar-actions :deep(button) {
    width: 100%;
  }
}
</style>
