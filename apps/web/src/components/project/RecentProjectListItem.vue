<script setup lang="ts">
import { ElButton, ElIcon, ElProgress, ElTag } from 'element-plus'
import { Delete } from '@element-plus/icons-vue'
import type { ProjectCardView } from './recentProjectsTypes'

const props = defineProps<{
  card: ProjectCardView
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

function tagTone(type: ProjectCardView['tags'][number]['type'] | ProjectCardView['tone']) {
  return type === 'danger' ? 'danger' : type === 'warning' ? 'warning' : type === 'success' ? 'success' : 'info'
}

function progressStatus(statusLabel: string) {
  return statusLabel === '失败' ? 'exception' : statusLabel === '已完成' ? 'success' : undefined
}
</script>

<template>
  <div class="project-item" :class="[card.tone, { selected: selectionMode && card.selected }]">
    <div class="project-main">
      <div class="project-info">
        <div class="project-head">
          <h4 class="project-title">{{ card.project.title }}</h4>
          <ElTag :type="tagTone(card.tone)" size="small">{{ card.statusLabel }}</ElTag>
        </div>
        <p class="project-hint">{{ card.stageText }} · {{ card.statusLabel }}</p>
        <div class="project-tags">
          <ElTag v-for="tag in card.tags" :key="`${card.project.id}-${tag.label}`" :type="tag.type" size="small">{{ tag.label }}</ElTag>
          <ElTag type="info" effect="plain" size="small">{{ card.materialModeLabel }}</ElTag>
        </div>
        <div class="project-health">
          <span v-if="card.emphasizeAssetIssues && card.missingAssetCount > 0" class="health-chip bad">{{ card.missingAssetLabel }} {{ card.missingAssetCount }}</span>
          <span v-if="card.duplicateAssetCount > 0" class="health-chip warn">重复素材 {{ card.duplicateAssetCount }}</span>
          <span v-if="card.continueStageLabel" class="health-chip">可从 {{ card.continueStageLabel }} 继续</span>
        </div>
        <div class="project-notice">{{ card.notice }}</div>
      </div>

      <div class="project-meta">
        <span class="project-time">更新于 {{ card.updatedAtText }}</span>
      </div>
    </div>

    <div class="execution-panel">
      <div class="execution-head">
        <div class="execution-title">{{ card.currentJobIsActive ? '当前执行' : '最近一次执行' }}</div>
        <div class="execution-summary">{{ card.currentJob ? `${card.currentJobKindLabel} · ${card.currentJobStageLabel}` : `${card.stageText} · ${card.statusLabel}` }}</div>
      </div>

      <template v-if="card.currentJob">
        <div class="execution-tags">
          <ElTag size="small">{{ card.currentJobKindLabel }}</ElTag>
          <ElTag :type="tagTone(card.tone)" size="small">{{ card.currentJobStatusLabel }}</ElTag>
          <ElTag v-if="card.currentJobSubstageLabel" type="info" effect="plain" size="small">{{ card.currentJobSubstageLabel }}</ElTag>
          <ElTag v-if="card.currentJobResumeLabel" type="info" effect="plain" size="small">{{ card.currentJobResumeLabel }}</ElTag>
        </div>
        <div class="execution-time">最近更新于 {{ card.currentJobUpdatedAtText }}</div>
        <div v-if="card.chainAttemptsLabel" class="execution-time">{{ card.chainAttemptsLabel }}</div>
        <ElProgress class="execution-progress" :percentage="card.currentJobProgress" :status="progressStatus(card.currentJobStatusLabel)" :stroke-width="8" />
        <div v-if="card.currentJobStageSummary && card.currentJobStageSummary !== card.currentJobStageLabel" class="execution-time">当前：{{ card.currentJobStageSummary }}</div>
        <div v-if="card.currentJobMessage" class="execution-message">{{ card.currentJobMessage }}</div>
        <div v-if="card.currentJobHint" class="execution-hint">{{ card.currentJobHint }}</div>
      </template>

      <template v-else>
        <div class="execution-empty">{{ card.notice }}</div>
      </template>
    </div>

    <div class="project-actions">
      <ElButton type="primary" size="small" @click="emit('openProject', card.project.id)">打开项目</ElButton>
      <ElButton v-if="card.finalExists" size="small" @click="emit('openFinal', card.project.id)">打开成片</ElButton>
      <ElButton v-if="card.needsLlmSettings" size="small" @click="emit('goSettings', 'llm')">去设置（大模型）</ElButton>
      <ElButton v-if="card.needsMediaSettings" size="small" @click="emit('goSettings', 'media')">去设置（素材）</ElButton>
      <ElButton v-if="card.needsTtsSettings" size="small" @click="emit('goSettings', 'tts')">去设置（配音）</ElButton>
      <ElButton
        v-if="selectionMode"
        size="small"
        :disabled="bulkDeleting || !card.canDelete"
        :type="card.selected ? 'primary' : 'default'"
        @click="emit('toggleSelect', card.project.id)"
      >
        {{ card.selected ? '已选中' : '选中' }}
      </ElButton>
      <ElButton
        v-else
        type="danger"
        size="small"
        :disabled="deletingProjectId === card.project.id || bulkDeleting"
        :loading="deletingProjectId === card.project.id"
        @click="emit('deleteProject', card.project.id)"
      >
        <ElIcon class="el-icon--left"><Delete /></ElIcon>
        删除项目
      </ElButton>
    </div>
  </div>
</template>

<style scoped>
.project-item {
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: 16px;
  background: #ffffff;
  transition: all 0.25s ease;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
}

.project-item:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.12);
}

.project-item.danger {
  border-color: rgba(180, 35, 24, 0.2);
  background: rgba(180, 35, 24, 0.05);
}

.project-item.warning {
  border-color: rgba(180, 83, 9, 0.18);
  background: rgba(180, 83, 9, 0.05);
}

.project-item.success {
  border-color: rgba(21, 128, 61, 0.16);
  background: rgba(21, 128, 61, 0.05);
}

.project-item.selected {
  border-color: var(--el-color-primary);
  background: rgba(29, 78, 216, 0.06);
}

.project-main {
  display: flex;
  justify-content: space-between;
  gap: 16px;
}

.project-info {
  flex: 1;
  min-width: 0;
}

.project-head {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}

.project-title {
  font-size: 15px;
  font-weight: 700;
  margin: 0;
}

.project-hint,
.project-time {
  font-size: 12px;
  color: var(--ink-soft);
}

.project-hint {
  margin: 8px 0;
}

.project-tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.project-notice {
  margin-top: 10px;
  line-height: 1.55;
  color: var(--ink-soft);
  white-space: pre-wrap;
}

.project-health {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 10px;
}

.health-chip {
  border-radius: 999px;
  padding: 3px 8px;
  font-size: 12px;
  line-height: 1.4;
  color: var(--ink-soft);
  background: rgba(15, 23, 42, 0.05);
}

.health-chip.warn {
  color: #9a6700;
  background: rgba(245, 158, 11, 0.12);
}

.health-chip.bad {
  color: #b42318;
  background: rgba(239, 68, 68, 0.12);
}

.project-meta {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 6px;
}

.execution-panel {
  margin-top: 14px;
  padding: 14px;
  border-radius: 10px;
  border: 1px solid rgba(15, 23, 42, 0.08);
  background: rgba(15, 23, 42, 0.025);
}

.execution-head {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
  align-items: center;
}

.execution-title {
  font-size: 13px;
  font-weight: 700;
}

.execution-summary,
.execution-time,
.execution-message,
.execution-hint,
.execution-empty {
  font-size: 12px;
  color: var(--ink-soft);
  line-height: 1.55;
}

.execution-tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-top: 10px;
}

.execution-time,
.execution-progress,
.execution-message,
.execution-hint,
.execution-empty,
.execution-jump {
  margin-top: 10px;
}

.project-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 14px;
}

@media (max-width: 900px) {
  .project-main {
    flex-direction: column;
  }

  .project-meta {
    align-items: flex-start;
  }

  .execution-head {
    flex-direction: column;
    align-items: flex-start;
  }
}

@media (max-width: 768px) {
  .project-actions :deep(button) {
    width: 100%;
  }
}
</style>
