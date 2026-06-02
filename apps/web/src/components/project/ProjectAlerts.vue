<script setup lang="ts">
import ErrorAlert from '../system/ErrorAlert.vue'

type AlertModel = {
  info?: string
  saveErr?: string
  err?: string
  onCloseInfo?: () => void
  onCloseSaveErr?: () => void
  onCloseErr?: () => void
  onRetry?: () => void
}

defineProps<{
  model: AlertModel
}>()
</script>

<template>
  <div class="project-alerts">
    <ErrorAlert 
      v-if="model.err" 
      :message="model.err" 
      type="error"
      :show-close="true"
      :show-retry="true"
      @close="model.onCloseErr?.()"
      @retry="model.onRetry?.()"
    />
    <ErrorAlert 
      v-if="model.saveErr" 
      :message="model.saveErr" 
      type="error"
      :show-close="true"
      @close="model.onCloseSaveErr?.()"
    />
    <div v-if="model.info" class="info">
      {{ model.info }}
      <button v-if="model.onCloseInfo" class="close-btn" @click="model.onCloseInfo">×</button>
    </div>
  </div>
</template>

<style scoped>
.project-alerts {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 16px;
}

.info {
  white-space: pre-wrap;
  padding: 12px 14px;
  border-radius: var(--radius-md);
  font-size: 13px;
  color: #0f5f4a;
  border: 1px solid rgba(15, 118, 110, 0.16);
  background: rgba(15, 118, 110, 0.06);
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 8px;
}

.close-btn {
  background: none;
  border: none;
  font-size: 18px;
  cursor: pointer;
  color: inherit;
  opacity: 0.6;
  padding: 0;
  line-height: 1;
}

.close-btn:hover {
  opacity: 1;
}
</style>
