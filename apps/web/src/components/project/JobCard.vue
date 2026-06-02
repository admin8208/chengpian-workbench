<script setup lang="ts">
import { ElButton, ElTag } from 'element-plus'
import type { Job, JobCenterItem } from '../../api/types'

const props = defineProps<{
  entry: JobCenterItem
  job: Job
  jobActionBusy: boolean
  normalizeStatus: (status: string) => string
  statusTagType: (status: string) => string
  openProject: (job: Job) => void
  openFinal: (job: Job) => void
  pauseJob: (job: Job) => void
  resumeJob: (job: Job) => void
  cancelJob: (job: Job) => void
  retryJob: (job: Job) => void
  deleteJob: (job: Job) => void
  isChainExpanded?: (rootId: number) => boolean
  toggleChain?: (rootId: number) => void
}>()

const displayJob = props.job
</script>

<template>
  <div class="job-main">
    <div class="job-head">
      <div>
        <div class="job-title">{{ entry.project_title }} · {{ entry.job_kind_label }}</div>
        <div class="muted">
          <template v-if="entry.entry_type === 'chain'">{{ entry.chain_attempts_label || `共 ${entry.attempt_count} 条记录` }} · 更新于 {{ entry.updated_at_text }}</template>
          <template v-else>任务 #{{ entry.job_id }} · 更新于 {{ entry.updated_at_text }}</template>
        </div>
      </div>
      <ElTag :type="statusTagType(entry.status) as any">{{ entry.status_label }}</ElTag>
    </div>

    <div class="job-meta">
      <span>阶段：{{ entry.stage_label || '-' }}</span>
      <span v-if="entry.substage_label">子阶段：{{ entry.substage_label }}</span>
      <span>进度：{{ Number(entry.progress || 0) }}%</span>
      <span v-if="entry.chain_attempts_label">{{ entry.chain_attempts_label }}</span>
    </div>

    <div class="job-message">{{ entry.message_label || '暂无任务说明。' }}</div>
    <div v-if="entry.human_hint" class="job-message muted">{{ entry.human_hint }}</div>

    <div v-if="['failed', 'cancelled'].includes(normalizeStatus(entry.status)) && (entry.error_code_label || entry.blocking_component_label || entry.recommended_action_label)" class="job-error muted">
      <span v-if="entry.error_code_label">错误：{{ entry.error_code_label }}</span>
      <span v-if="entry.blocking_component_label">阻塞点：{{ entry.blocking_component_label }}</span>
      <span v-if="entry.recommended_action_label">建议：{{ entry.recommended_action_label }}</span>
    </div>

    <div v-if="entry.entry_type === 'chain' && entry.history.length > 1 && isChainExpanded && toggleChain" class="chain-panel">
      <button class="chain-toggle" type="button" @click="toggleChain(Number(entry.root_job_id || entry.job_id))">
        {{ isChainExpanded(Number(entry.root_job_id || entry.job_id)) ? '收起历史' : `展开历史（${entry.history.length - 1} 条旧记录）` }}
      </button>
      <div v-if="isChainExpanded(Number(entry.root_job_id || entry.job_id))" class="chain-history">
        <div v-for="historyJob in entry.history" :key="historyJob.job_id" class="chain-history-item">
          <div class="chain-history-top">
            <div class="chain-history-title">#{{ historyJob.job_id }} · {{ historyJob.execution_label }}</div>
            <ElTag size="small" :type="statusTagType(historyJob.status) as any">{{ historyJob.status_label }}</ElTag>
          </div>
          <div class="muted">{{ historyJob.stage_label || '-' }}<span v-if="historyJob.substage_label"> · {{ historyJob.substage_label }}</span> · 更新于 {{ historyJob.updated_at_text }}</div>
        </div>
      </div>
    </div>
  </div>

  <div class="job-actions">
    <ElButton size="small" @click="openProject(displayJob)">打开项目</ElButton>
    <ElButton v-if="entry.project_final_exists" size="small" @click="openFinal(displayJob)">打开成片</ElButton>
    <ElButton v-if="['queued', 'running'].includes(normalizeStatus(entry.status))" size="small" :disabled="jobActionBusy" @click="pauseJob(displayJob)">暂停</ElButton>
    <ElButton v-if="normalizeStatus(entry.status) === 'paused'" size="small" :disabled="jobActionBusy" @click="resumeJob(displayJob)">继续</ElButton>
    <ElButton v-if="!['done', 'failed', 'cancelled'].includes(normalizeStatus(entry.status))" size="small" type="danger" plain :disabled="jobActionBusy" @click="cancelJob(displayJob)">取消</ElButton>
    <ElButton v-if="['failed', 'cancelled'].includes(normalizeStatus(entry.status))" size="small" type="primary" plain :disabled="jobActionBusy" @click="retryJob(displayJob)">继续</ElButton>
    <ElButton v-if="entry.is_deletable" size="small" type="danger" plain :disabled="jobActionBusy" @click="deleteJob(displayJob)">删除任务</ElButton>
  </div>
</template>

<style scoped>
.job-main {
  flex: 1;
  min-width: 0;
}

.job-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
}

.job-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--ink);
}

.job-meta {
  margin-top: 10px;
  display: flex;
  gap: 14px;
  flex-wrap: wrap;
  color: var(--ink-soft);
  font-size: 13px;
}

.job-message {
  margin-top: 10px;
  color: var(--ink);
  line-height: 1.6;
}

.job-error {
  margin-top: 8px;
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.job-actions {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-width: 120px;
}

.chain-panel {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px dashed var(--line);
}

.chain-toggle {
  border: 0;
  background: transparent;
  padding: 0;
  color: var(--brand);
  cursor: pointer;
  font: inherit;
  font-weight: 600;
}

.chain-history {
  margin-top: 10px;
  display: grid;
  gap: 8px;
}

.chain-history-item {
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 10px 12px;
  background: color-mix(in srgb, var(--panel) 78%, transparent);
}

.chain-history-top {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: center;
  margin-bottom: 4px;
}

.chain-history-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--ink);
}

@media (max-width: 900px) {
  .job-actions {
    min-width: 0;
    flex-direction: row;
    flex-wrap: wrap;
  }
}
</style>
