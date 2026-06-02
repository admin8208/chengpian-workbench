<script setup lang="ts">
import { ElAlert, ElButton, ElCheckbox, ElEmpty, ElSelect, ElOption } from 'element-plus'
import JobCard from '../../components/project/JobCard.vue'
import { useJobsView } from './useJobsView'

const {
  jobs,
  loading,
  err,
  filterStatus,
  taskScope,
  deletingProject,
  projectionRebuilding,
  runtimeWarning,
  selectionMode,
  bulkDeletingJobs,
  selectedProjectId,
  jobActionBusy,
  statusOptions,
  taskScopeOptions,
  statusOptionMap,
  taskScopeOptionMap,
  visibleJobs,
  visibleJobMap,
  visibleEntries,
  deletableVisibleEntries,
  selectedDeletableEntries,
  allDeletableVisibleSelected,
  stats,
  normalizeStatus,
  load,
  isChainExpanded,
  toggleChain,
  openProject,
  openFinal,
  statusTagType,
  canDeleteEntry,
  isSelectedEntry,
  setSelectionMode,
  toggleEntrySelection,
  selectAllVisibleEntries,
  clearSelectedEntries,
  pauseJob,
  resumeJob,
  cancelJob,
  retryJob,
  deleteJob,
  deleteSelectedJobs,
  deleteSelectedProject,
} = useJobsView()
</script>

<template>
  <div class="jobs-view">
    <section class="card heroPanel" style="margin-top: 16px; padding: 20px;">
      <div class="hero-top">
        <div>
          <div class="eyebrow">任务中心</div>
          <h2 class="section-title">全局任务与执行状态</h2>
          <div class="muted intro">这里是任务操作面板。默认只展示项目生成相关任务；系统任务如离线音色安装、备份等不会混入主视图。</div>
          <div v-if="selectedProjectId > 0" class="muted intro">当前已按项目 #{{ selectedProjectId }} 过滤，只显示这个项目的执行记录。</div>
        </div>
        <div class="hero-actions">
          <ElButton v-if="selectedProjectId > 0" type="danger" plain :loading="deletingProject" @click="deleteSelectedProject">删除当前项目</ElButton>
          <ElSelect v-model="taskScope" style="width: 140px">
            <ElOption v-for="item in taskScopeOptions" :key="item.value" :label="item.label" :value="item.value" />
          </ElSelect>
          <ElSelect v-model="filterStatus" style="width: 140px">
            <ElOption v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" />
          </ElSelect>
          <ElButton @click="load" :loading="loading">刷新</ElButton>
        </div>
      </div>

      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-label">全部任务</div>
          <div class="stat-value">{{ stats.all }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">进行中</div>
          <div class="stat-value">{{ stats.active }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">失败</div>
          <div class="stat-value">{{ stats.failed }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">已完成</div>
          <div class="stat-value">{{ stats.done }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">已取消</div>
          <div class="stat-value">{{ stats.cancelled }}</div>
        </div>
      </div>

      <ElAlert v-if="err" type="error" show-icon closable @close="err = ''" style="margin-top: 16px" :title="err" />
      <ElAlert v-if="runtimeWarning && !err" type="warning" show-icon closable @close="runtimeWarning = ''" style="margin-top: 16px" :title="runtimeWarning" />
      <ElAlert v-if="projectionRebuilding && !err && !runtimeWarning" type="info" show-icon :closable="false" style="margin-top: 16px" title="任务索引正在后台构建，当前先显示空列表；稍后会自动刷新。" />
    </section>

    <section class="card" style="margin-top: 16px; padding: 20px;">
      <div class="list-toolbar">
        <div class="muted toolbar-note">
          {{ selectionMode ? `已选 ${selectedDeletableEntries.length} 个可删除任务视图，仅可删除非进行中任务。` : `当前列表：${taskScopeOptionMap[taskScope] || '项目任务'} · ${statusOptionMap[filterStatus] || '全部'} · 共 ${visibleEntries.length} 个任务视图（原始记录 ${visibleJobs.length} 条）` }}
        </div>
        <div class="toolbar-actions">
          <ElButton :disabled="bulkDeletingJobs" @click="setSelectionMode(!selectionMode)">{{ selectionMode ? '取消选择' : '批量选择' }}</ElButton>
          <ElButton v-if="selectionMode" :disabled="bulkDeletingJobs || !deletableVisibleEntries.length" @click="allDeletableVisibleSelected ? clearSelectedEntries() : selectAllVisibleEntries()">
            {{ allDeletableVisibleSelected ? '清空已选' : '全选可删除' }}
          </ElButton>
          <ElButton v-if="selectionMode" type="danger" :disabled="bulkDeletingJobs || !selectedDeletableEntries.length" :loading="bulkDeletingJobs" @click="deleteSelectedJobs">
            批量删除任务
          </ElButton>
        </div>
      </div>
      <div v-if="loading && !jobs.length" class="muted">正在加载任务列表…</div>
      <ElEmpty v-else-if="!visibleEntries.length" description="当前筛选下没有任务记录。" />
      <div v-else class="job-list">
        <article v-for="entry in visibleEntries" :key="entry.entry_key" class="job-card" :class="{ selectable: selectionMode, selected: isSelectedEntry(entry), disabledSelect: selectionMode && !canDeleteEntry(entry) }">
          <div v-if="selectionMode" class="job-select">
            <ElCheckbox :model-value="isSelectedEntry(entry)" :disabled="bulkDeletingJobs || !canDeleteEntry(entry)" @change="toggleEntrySelection(entry)" />
          </div>
          <JobCard
            :entry="entry"
            :job="visibleJobMap.get(entry.job_id)!"
            :job-action-busy="jobActionBusy"
            :normalize-status="normalizeStatus"
            :status-tag-type="statusTagType"
            :open-project="openProject"
            :open-final="openFinal"
            :pause-job="pauseJob"
            :resume-job="resumeJob"
            :cancel-job="cancelJob"
            :retry-job="retryJob"
            :delete-job="deleteJob"
            :is-chain-expanded="isChainExpanded"
            :toggle-chain="toggleChain"
          />
        </article>
      </div>
    </section>
  </div>
</template>

<style scoped>
.jobs-view {
  margin: 0 auto;
  padding: 0 16px;
}

.hero-top {
  display: flex;
  justify-content: space-between;
  gap: 20px;
  align-items: flex-start;
}

.hero-actions {
  display: flex;
  gap: 12px;
  align-items: center;
}

.eyebrow {
  color: var(--brand);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.intro {
  margin-top: 8px;
  line-height: 1.7;
  max-width: 760px;
}

.stats-grid {
  margin-top: 18px;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 12px;
}

.stat-card {
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 14px 16px;
  background: color-mix(in srgb, var(--panel) 82%, transparent);
}

.stat-label {
  color: var(--ink-soft);
  font-size: 12px;
}

.stat-value {
  margin-top: 6px;
  font-size: 28px;
  font-weight: 800;
  color: var(--ink);
}

.job-list {
  display: grid;
  gap: 14px;
}

.list-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 12px;
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

.job-card {
  border: 1px solid var(--line);
  border-radius: 16px;
  padding: 16px;
  display: flex;
  justify-content: space-between;
  gap: 18px;
  background: color-mix(in srgb, var(--panel) 86%, transparent);
}

.job-card.selectable {
  cursor: pointer;
}

.job-card.selected {
  border-color: var(--brand);
  box-shadow: 0 0 0 1px color-mix(in srgb, var(--brand) 42%, transparent);
}

.job-card.disabledSelect {
  opacity: 0.72;
  cursor: not-allowed;
}

.job-select {
  display: flex;
  align-items: flex-start;
  padding-top: 2px;
}

@media (max-width: 900px) {
  .hero-top,
  .job-card {
    flex-direction: column;
  }

  .hero-actions,
  .toolbar-actions {
    width: 100%;
  }

  .toolbar-actions :deep(button) {
    width: 100%;
  }

  .stats-grid {
    grid-template-columns: 1fr;
  }
}
</style>
