<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElAlert, ElButton, ElEmpty, ElMessage, ElSkeleton } from 'element-plus'
import { api, type Project } from '../../api'
import RecentProjectList from '../../components/project/RecentProjectList.vue'
import ProjectCenterHeader from './components/ProjectCenterHeader.vue'
import ProjectCenterStats from './components/ProjectCenterStats.vue'
import ProjectCenterToolbar from './components/ProjectCenterToolbar.vue'
import { useRecentProjectsAutoRefresh } from './useRecentProjectsAutoRefresh'
import { useRecentProjectsData } from './useRecentProjectsData'
import { useRecentProjectsDeletion } from './useRecentProjectsDeletion'
import { useRecentProjectsSelection } from './useRecentProjectsSelection'
import { useRecentProjectsViewModel } from './useRecentProjectsViewModel'

const router = useRouter()

const { feed, projects, err, runtimeWarning, projectionRebuilding, pageLoading, lastUpdateTime, visibleProjects, load, retryLoad } = useRecentProjectsData()

function clearRuntimeWarning() {
  runtimeWarning.value = ''
}

function projectDeleteBlockedReason(p: Project) {
  const status = String(primaryJob(p)?.status || activeJobStatus(p) || '').trim().toLowerCase()
  if (status === 'running') return '该项目正在生成中，先等待完成或直接取消当前执行。'
  return ''
}

function canDeleteProject(p: Project) {
  return !projectDeleteBlockedReason(p)
}

function projectHasQueuedJob(p: Project) {
  return String(primaryJob(p)?.status || activeJobStatus(p) || '').trim().toLowerCase() === 'queued'
}

const bulkDeleting = ref(false)

const {
  selectionMode,
  selectedProjectIds,
  isSelectedProject,
  setSelectionMode,
  toggleProjectSelection,
  deletableVisibleProjects,
  allDeletableVisibleSelected,
  selectAllVisibleProjects,
  clearSelectedProjects,
} = useRecentProjectsSelection({ visibleProjects, bulkDeleting, canDeleteProject })

const { deletingProjectId, deleteProject, deleteSelectedProjects } = useRecentProjectsDeletion({
  visibleProjects,
  selectedProjectIds,
  selectionMode,
  bulkDeleting,
  err,
  load,
  canDeleteProject,
  projectDeleteBlockedReason,
  projectHasQueuedJob,
})

const autoRefreshBusy = computed(() => bulkDeleting.value || deletingProjectId.value !== null)

const {
  primaryJob,
  activeJobStatus,
  projectCards,
  runningProjectCount,
  failedProjectCount,
  finalProjectCount,
} = useRecentProjectsViewModel({
  projects: visibleProjects,
  feedItems: computed(() => feed.value?.items || []),
  isSelectedProject,
})

function openProject(p: Project) {
  const mode = String(p.render_config?.material_mode || '').trim().toLowerCase()
  router.push({ path: mode === 'ai' ? `/p/ai/${p.id}` : `/p/network/${p.id}` })
}

async function openFinal(p: Project) {
  try {
    const fin = await api.finalExport(p.id)
    if (!fin.exists || !fin.url) {
      ElMessage.info(`项目《${p.title}》当前还没有最终成片文件。`)
      return
    }
    window.open(fin.url, '_blank')
  } catch (e: any) {
    ElMessage.error(e?.message ?? String(e))
  }
}

function findProjectById(projectId: number) {
  return visibleProjects.value.find((p) => p.id === projectId) || null
}

function openProjectById(projectId: number) {
  const project = findProjectById(projectId)
  if (project) openProject(project)
}

async function openFinalById(projectId: number) {
  const project = findProjectById(projectId)
  if (project) await openFinal(project)
}

function toggleProjectSelectionById(projectId: number) {
  const project = findProjectById(projectId)
  if (project) toggleProjectSelection(project)
}

async function deleteProjectById(projectId: number) {
  const project = findProjectById(projectId)
  if (project) await deleteProject(project)
}

function goSettings(tab: 'llm' | 'media' | 'tts') {
  router.push({ path: '/settings', query: { tab } })
}

useRecentProjectsAutoRefresh({ pageLoading, jobActionBusy: autoRefreshBusy, retryLoad })

onMounted(() => {
  const deleted = Number(router.currentRoute.value.query.deleted || 0)
  if (!Number.isFinite(deleted) || deleted <= 0) return
  ElMessage.info(`项目 #${deleted} 已删除。`)
  void router.replace({ path: '/recent' })
})
</script>

<template>
  <div class="project-center-view">
    <section class="heroPanel card" style="margin-top: 16px; padding: 20px;">
      <ProjectCenterHeader :last-update-time="lastUpdateTime" :page-loading="pageLoading" @refresh="retryLoad()" />
      <div class="muted" style="margin-bottom: 16px; line-height: 1.6">这里统一管理项目内容与产物，只回答“这个项目现在是什么状态、还缺什么、下一步该去哪”。</div>

      <ProjectCenterStats :project-count="projects.length" :running-project-count="runningProjectCount" :failed-project-count="failedProjectCount" :final-project-count="finalProjectCount" />

      <ElAlert v-if="err" type="error" show-icon closable @close="err = ''" style="margin-top: 16px">
        <template #title>
          <div style="display: flex; align-items: center; justify-content: space-between; width: 100%;">
            <span>{{ err }}</span>
            <ElButton size="small" type="danger" @click="retryLoad()" style="margin-left: 12px;">重试</ElButton>
          </div>
        </template>
      </ElAlert>

      <ElAlert v-if="runtimeWarning && !err" type="warning" show-icon closable @close="clearRuntimeWarning" style="margin-top: 16px">
        <template #title>
          <div style="display: flex; align-items: center; justify-content: space-between; width: 100%;">
            <span>{{ runtimeWarning }}</span>
            <ElButton size="small" @click="retryLoad()" style="margin-left: 12px;">重试</ElButton>
          </div>
        </template>
      </ElAlert>

      <ElAlert v-if="projectionRebuilding && !err" type="info" show-icon :closable="false" style="margin-top: 16px" title="项目索引正在后台构建，当前先显示空列表；稍后会自动刷新。" />
    </section>

    <section class="card" style="margin-top: 16px; padding: 20px;">
      <ProjectCenterToolbar
        :selection-mode="selectionMode"
        :selected-count="selectedProjectIds.length"
        :bulk-deleting="bulkDeleting"
        :deletable-visible-count="deletableVisibleProjects.length"
        :all-deletable-visible-selected="allDeletableVisibleSelected"
        @toggle-selection-mode="setSelectionMode(!selectionMode)"
        @toggle-select-all="allDeletableVisibleSelected ? clearSelectedProjects() : selectAllVisibleProjects()"
        @delete-selected="deleteSelectedProjects"
      />

      <ElSkeleton v-if="pageLoading && !projects.length" :rows="6" animated>
        <template #template>
          <div style="padding: 20px;">
            <ElSkeleton :rows="6" animated />
          </div>
        </template>
      </ElSkeleton>

      <template v-else>
        <ElEmpty v-if="projects.length === 0" description="">
          <div style="text-align: center;">
            <ElButton type="primary" size="large" @click="router.push('/creator/ai')" style="margin-bottom: 12px;">
              去智能创作
            </ElButton>
            <ElButton size="large" @click="router.push('/creator/network')" style="margin-bottom: 12px;">
              去素材创作
            </ElButton>
            <div style="color: var(--ink-soft); font-size: 14px;">
            </div>
          </div>
        </ElEmpty>

        <RecentProjectList
          v-else
          :cards="projectCards"
          :selection-mode="selectionMode"
          :bulk-deleting="bulkDeleting"
          :deleting-project-id="deletingProjectId"
          @open-project="openProjectById"
          @open-final="openFinalById"
          @go-settings="goSettings"
          @toggle-select="toggleProjectSelectionById"
          @delete-project="deleteProjectById"
        />
      </template>
    </section>
  </div>
</template>

<style scoped>
.project-center-view {
  margin: 0 auto;
  padding: 0 16px;
}

.card {
  width: 100%;
  box-sizing: border-box;
}

.section-title {
  font-size: 18px;
  font-weight: 700;
  margin: 0 0 8px 0;
  color: var(--ink);
  line-height: 1.2;
  display: flex;
  align-items: center;
  gap: 8px;
}
</style>
