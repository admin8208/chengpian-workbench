<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElIcon, ElTag, ElCollapseTransition } from 'element-plus'
import { ArrowRight, Check, Warning, Loading } from '@element-plus/icons-vue'

interface Props {
  title: string
  desc: string
  stepKey: string
  isActive: boolean
  isCompleted: boolean
  isCurrent: boolean
  status: 'pending' | 'active' | 'running' | 'completed' | 'error'
  summary?: string
  defaultExpanded?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  defaultExpanded: false,
})

const expanded = ref(props.isActive || props.defaultExpanded)

// 当 isActive 变为 true 时自动展开面板
watch(() => props.isActive, (active) => {
  if (active) expanded.value = true
})

const headerClass = computed(() => ({
  'step-panel-header': true,
  active: props.isActive,
  completed: props.isCompleted,
  current: props.isCurrent,
  error: props.status === 'error',
}))

type TagType = 'success' | 'warning' | 'danger' | 'primary'

const statusTag = computed<{ type: TagType; label: string } | null>(() => {
  if (props.status === 'completed') return { type: 'success', label: '已完成' }
  if (props.status === 'running') return { type: 'warning', label: '执行中' }
  if (props.status === 'error') return { type: 'danger', label: '出错' }
  if (props.status === 'active') return { type: 'primary', label: '进行中' }
  return null
})

function toggleExpand() {
  expanded.value = !expanded.value
}
</script>

<template>
  <div class="step-panel" :class="{ active: isActive, collapsed: !expanded }">
    <div :class="headerClass" @click="toggleExpand">
      <div class="header-left">
        <ElIcon class="expand-icon" :class="{ expanded }">
          <ArrowRight />
        </ElIcon>
        <div class="header-info">
          <div class="header-title">
            <span class="title-text">{{ title }}</span>
            <ElTag v-if="statusTag" :type="statusTag.type" size="small">{{ statusTag.label }}</ElTag>
            <ElTag v-if="isCurrent && !isActive" type="info" size="small">当前步骤</ElTag>
          </div>
          <div class="header-desc">{{ desc }}</div>
          <div v-if="summary && !expanded" class="header-summary">{{ summary }}</div>
        </div>
      </div>
      <div class="header-right">
        <ElIcon v-if="status === 'running'" class="is-loading status-icon">
          <Loading />
        </ElIcon>
        <ElIcon v-else-if="status === 'completed'" class="status-icon check">
          <Check />
        </ElIcon>
        <ElIcon v-else-if="status === 'error'" class="status-icon error">
          <Warning />
        </ElIcon>
      </div>
    </div>

    <ElCollapseTransition>
      <div v-show="expanded" class="step-panel-content">
        <slot></slot>
      </div>
    </ElCollapseTransition>
  </div>
</template>

<style scoped>
.step-panel {
  border-radius: 20px;
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.78);
  overflow: hidden;
  transition: all 160ms ease;
}

html.dark .step-panel {
  background: rgba(30, 41, 59, 0.78);
}

.step-panel.active {
  border-color: rgba(29, 78, 216, 0.24);
  box-shadow: 0 4px 16px rgba(29, 78, 216, 0.08);
}

.step-panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  cursor: pointer;
  transition: all 160ms ease;
  user-select: none;
}

.step-panel-header:hover {
  background: rgba(0, 0, 0, 0.02);
}

html.dark .step-panel-header:hover {
  background: rgba(255, 255, 255, 0.02);
}

.step-panel-header.active {
  background: rgba(29, 78, 216, 0.04);
}

.step-panel-header.completed {
  opacity: 0.8;
}

.step-panel-header.completed:hover {
  opacity: 1;
}

.step-panel-header.error {
  background: rgba(180, 35, 24, 0.04);
}

.header-left {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  flex: 1;
  min-width: 0;
}

.expand-icon {
  font-size: 14px;
  color: var(--ink-soft);
  transition: transform 200ms ease;
  flex-shrink: 0;
  margin-top: 4px;
}

.expand-icon.expanded {
  transform: rotate(90deg);
}

.header-info {
  flex: 1;
  min-width: 0;
}

.header-title {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.title-text {
  font-size: 16px;
  font-weight: 700;
  color: var(--ink);
}

.header-desc {
  font-size: 13px;
  color: var(--ink-soft);
  margin-top: 4px;
}

.header-summary {
  font-size: 12px;
  color: var(--ink-faint);
  margin-top: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.status-icon {
  font-size: 18px;
}

.status-icon.check {
  color: rgba(21, 128, 61, 1);
}

.status-icon.error {
  color: rgba(180, 35, 24, 1);
}

.status-icon.is-loading {
  color: var(--el-color-warning);
}

.step-panel-content {
  padding: 0 20px 20px;
  border-top: 1px solid var(--line);
  margin-top: 0;
  padding-top: 20px;
}

.is-loading {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}
</style>
