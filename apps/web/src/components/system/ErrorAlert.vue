<script setup lang="ts">
import { computed } from 'vue'
import { ElIcon, ElButton } from 'element-plus'
import { Close, Warning, RefreshRight } from '@element-plus/icons-vue'

interface Props {
  message: string
  type?: 'error' | 'warning' | 'info'
  showClose?: boolean
  showRetry?: boolean
  retryText?: string
}

const props = withDefaults(defineProps<Props>(), {
  type: 'error',
  showClose: true,
  showRetry: false,
  retryText: '重试'
})

const emit = defineEmits<{
  'close': []
  'retry': []
}>()

const icon = computed(() => {
  switch (props.type) {
    case 'error':
      return Warning
    case 'warning':
      return Warning
    case 'info':
      return Warning
    default:
      return Warning
  }
})

const bgColor = computed(() => {
  switch (props.type) {
    case 'error':
      return 'rgba(239, 68, 68, 0.1)'
    case 'warning':
      return 'rgba(245, 158, 11, 0.1)'
    case 'info':
      return 'rgba(59, 130, 246, 0.1)'
    default:
      return 'rgba(239, 68, 68, 0.1)'
  }
})

const borderColor = computed(() => {
  switch (props.type) {
    case 'error':
      return 'rgba(239, 68, 68, 0.3)'
    case 'warning':
      return 'rgba(245, 158, 11, 0.3)'
    case 'info':
      return 'rgba(59, 130, 246, 0.3)'
    default:
      return 'rgba(239, 68, 68, 0.3)'
  }
})

const textColor = computed(() => {
  switch (props.type) {
    case 'error':
      return 'rgb(220, 38, 38)'
    case 'warning':
      return 'rgb(180, 83, 9)'
    case 'info':
      return 'rgb(37, 99, 235)'
    default:
      return 'rgb(220, 38, 38)'
  }
})

function handleClose() {
  emit('close')
}

function handleRetry() {
  emit('retry')
}
</script>

<template>
  <div 
    class="error-alert"
    :style="{
      backgroundColor: bgColor,
      borderColor: borderColor,
      color: textColor
    }"
  >
    <div class="alert-content">
      <ElIcon class="alert-icon"><component :is="icon" /></ElIcon>
      <div class="alert-message">{{ message }}</div>
    </div>
    <div class="alert-actions">
      <ElButton 
        v-if="showRetry" 
        type="text" 
        :icon="RefreshRight"
        @click="handleRetry"
        :style="{ color: textColor }"
      >
        {{ retryText }}
      </ElButton>
      <ElButton 
        v-if="showClose" 
        type="text" 
        :icon="Close"
        @click="handleClose"
        :style="{ color: textColor }"
      />
    </div>
  </div>
</template>

<style scoped>
.error-alert {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px;
  border-radius: 8px;
  border: 1px solid;
  margin-bottom: 16px;
  transition: all 0.3s ease;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
}

.alert-content {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  flex: 1;
  min-width: 0;
}

.alert-icon {
  font-size: 20px;
  flex-shrink: 0;
  margin-top: 2px;
}

.alert-message {
  flex: 1;
  font-size: 14px;
  line-height: 1.4;
  white-space: pre-wrap;
}

.alert-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .error-alert {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }
  
  .alert-actions {
    align-self: flex-end;
  }
}
</style>
