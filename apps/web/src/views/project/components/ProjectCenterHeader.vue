<script setup lang="ts">
import { ElButton } from 'element-plus'

defineProps<{
  lastUpdateTime: string
  pageLoading: boolean
}>()

const emit = defineEmits<{
  refresh: []
}>()
</script>

<template>
  <div class="headerRow">
    <h2 class="section-title headerTitle">项目中心</h2>
    <div class="headerActions">
      <span v-if="lastUpdateTime" class="headerMeta">最后更新: {{ lastUpdateTime }}</span>
      <ElButton size="small" :loading="pageLoading" @click="emit('refresh')">刷新</ElButton>
    </div>
  </div>
</template>

<style scoped>
.headerRow {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  gap: 12px;
  flex-wrap: wrap;
}

.headerTitle {
  margin-bottom: 0;
}

.headerActions {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.headerMeta {
  font-size: 12px;
  color: var(--ink-soft);
}
</style>
