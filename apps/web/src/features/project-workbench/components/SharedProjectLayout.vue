<script setup lang="ts">
import ProjectHeaderBar from '../../../components/project/ProjectHeaderBar.vue'
import ProjectInputStep from '../../../components/project/ProjectInputStep.vue'
import ProjectJobStatusBar from '../../../components/project/ProjectJobStatusBar.vue'
import ProjectRenderStep from '../../../components/project/ProjectRenderStep.vue'
import ProjectVoiceStep from '../../../components/project/ProjectVoiceStep.vue'
import ProjectAlerts from '../../../components/project/ProjectAlerts.vue'
import SectionIntro from '../../../components/shared/SectionIntro.vue'
import FlowNavSidebar from '../../../components/project/FlowNavSidebar.vue'
import StepPanel from '../../../components/project/StepPanel.vue'

defineProps<{ model: any }>()

type StepStatus = 'error' | 'running' | 'active' | 'pending' | 'completed'

function activeStepStatus(flowControl: any, current: boolean, completed: boolean, doneWhen?: boolean): StepStatus {
  const status = String(flowControl.jobStatus || '').trim().toLowerCase()
  if (current) {
    if (status === 'failed') return 'error'
    if (status === 'done' || doneWhen) return 'completed'
    if (status === 'running' || status === 'queued' || status === 'paused') return 'running'
    return 'active'
  }
  return completed ? 'completed' : 'pending'
}
</script>

<template>
  <div class="project-page">
    <section v-if="model.loadState === 'loading'" class="card" style="margin-top: 16px">
      <SectionIntro kicker="加载中" title="正在加载项目" desc="正在读取项目、镜头和成片数据，请稍候。" />
      <div class="muted" style="margin-top: 12px">{{ model.loadMessage }}</div>
    </section>

    <section v-else-if="model.loadState === 'error' || model.loadState === 'not_found'" class="card" style="margin-top: 16px">
      <SectionIntro :kicker="'项目'" :title="model.loadState === 'not_found' ? '项目不存在' : '项目加载失败'" :desc="model.loadState === 'not_found' ? '这个项目可能已删除，或者链接本身无效。' : '页面错误已经被拦住了；你可以直接重试或返回创作中心。'" />
      <div class="err" style="margin-top: 12px">{{ model.loadMessage }}</div>
      <div class="row" style="margin-top: 12px; flex-wrap: wrap">
        <button class="btn" @click="model.retryLoad">重试</button>
        <button class="btnGhost" @click="model.router.push(model.backRoute)">返回创作中心</button>
        <button v-if="model.loadState === 'error'" class="btnGhost" @click="model.router.push('/health')">打开健康检查</button>
      </div>
    </section>

    <template v-else-if="model.project">
      <ProjectHeaderBar :model="{ project: model.project, titleInput: model.flowControl.titleInput, back: model.flowControl.back }" />

      <div class="project-layout">
        <aside class="project-sidebar">
          <FlowNavSidebar :model="model.flowControl" />
        </aside>

        <main class="project-content">
          <ProjectJobStatusBar :model="model.flowControl" />
          <ProjectAlerts :model="{ info: model.info, saveErr: model.saveErr, err: model.err, onCloseInfo: () => (model.info = ''), onCloseSaveErr: () => (model.saveErr = ''), onCloseErr: () => (model.err = ''), onRetry: model.flowControl.visibleJobBar ? model.flowControl.retryCurrentJob : model.retryLoad }" />

          <ProjectInputStep
            :current-step="model.currentStep"
            :auto-step="model.autoStep"
            :step-status="activeStepStatus(model.flowControl, model.currentStep === 'input', model.stepIndex(model.currentStep) > 0)"
            :is-completed="model.stepIndex(model.currentStep) > 0"
            :model="model.inputStep"
          />

          <StepPanel
            v-if="model.currentStep === 'storyboard'"
            title="脚本分镜"
            desc="根据已确认的文案或转写结果，生成镜头结构、旁白分段和画面提示。"
            step-key="storyboard"
            :is-active="model.currentStep === 'storyboard'"
            :is-completed="model.stepIndex(model.currentStep) > 1"
            :is-current="model.autoStep === 'storyboard'"
            :status="activeStepStatus(model.flowControl, model.currentStep === 'storyboard', model.stepIndex(model.currentStep) > 1)"
            :summary="`${model.project.scenes?.length || 0} 个镜头`"
            :default-expanded="model.currentStep === 'storyboard'"
            style="margin-top: 16px"
          >
            <div class="softItem muted" style="margin: 20px; line-height: 1.6">
              当前项目已有 {{ model.project.scenes?.length || 0 }} 个镜头。脚本分镜阶段只负责内容结构，画面缺失、重复素材和生图问题会在下一步“画面准备”集中处理。
            </div>
          </StepPanel>

          <ProjectVoiceStep
            :current-step="model.currentStep"
            :auto-step="model.autoStep"
            :step-status="activeStepStatus(model.flowControl, model.currentStep === 'voice', model.stepIndex(model.currentStep) > 2)"
            :is-completed="model.stepIndex(model.currentStep) > 2"
            :model="model.voiceStep"
          />

          <slot name="media" :step-status="activeStepStatus(model.flowControl, model.currentStep === 'media', model.stepIndex(model.currentStep) > 3)" />

          <ProjectRenderStep
            :current-step="model.currentStep"
            :auto-step="model.autoStep"
            :step-status="activeStepStatus(model.flowControl, model.currentStep === 'render', Boolean(model.finalStatus?.exists), Boolean(model.finalStatus?.exists))"
            :model="model.renderStep"
            @update:selected-video-url="model.renderStep.selectedVideoUrl = $event"
          />
        </main>
      </div>
    </template>
  </div>
</template>

<style scoped>
.project-page {
  max-width: 1600px;
  margin: 0 auto;
  padding-bottom: 40px;
}

.project-layout {
  display: grid;
  grid-template-columns: 280px 1fr;
  gap: 16px;
  align-items: start;
}

.project-sidebar {
  position: sticky;
  top: 80px;
}

.project-content {
  min-width: 0;
}

@media (max-width: 1024px) {
  .project-layout {
    grid-template-columns: 1fr;
  }

  .project-sidebar {
    position: static;
  }
}
</style>
