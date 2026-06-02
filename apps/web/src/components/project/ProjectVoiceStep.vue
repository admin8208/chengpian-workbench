<script setup lang="ts">
import type { ProjectDetail } from '../../api'
import StepPanel from './StepPanel.vue'

type StepStatus = 'error' | 'running' | 'active' | 'pending' | 'completed'

type VoiceStepModel = {
  project: ProjectDetail | null
  inputMode?: 'text' | 'audio'
  projectVoiceRateLabel: string
  currentTtsBackendLabel: string
  currentTtsVoiceLabel: string
  subtitlePreviewText: string
  subtitlePreviewBusy: boolean
  subtitlePreviewErr: string
}

defineProps<{
  currentStep: string
  autoStep: string
  stepStatus: StepStatus
  isCompleted: boolean
  model: VoiceStepModel
}>()

function narrationSummary(project: ProjectDetail) {
  const scenes = Array.isArray(project?.scenes) ? project.scenes : []
  return scenes.map((scene) => `镜头 ${scene.idx}：${scene.narration || '（无旁白）'}`).join('\n')
}
</script>

<template>
  <StepPanel
    v-if="currentStep === 'voice'"
    :title="model.inputMode === 'audio' ? '音轨与字幕' : '配音与字幕'"
    :desc="model.inputMode === 'audio' ? '这一页会直接复用上传音频，并把字幕收口成可发布状态。' : '这一页只负责把声音和字幕收口成安全、统一、可发布的状态。'"
    step-key="voice"
    :is-active="currentStep === 'voice'"
    :is-completed="isCompleted"
    :is-current="autoStep === 'voice'"
    :status="stepStatus"
    :default-expanded="currentStep === 'voice'"
    style="margin-top: 16px"
  >
    <div class="step-content-inner">
      <div class="softItem muted rate-box">
        <div class="rate-title">{{ model.inputMode === 'audio' ? '项目音频说明' : '当前配音语速' }}</div>
        <div class="muted rate-copy">{{ model.inputMode === 'audio' ? '当前项目会直接复用上传主音频；全局语速设置不会影响已上传音频。' : '配音语速现在由“设置 -> 配音”统一控制，这里只展示当前全局生效值。' }}</div>
        <div v-if="model.inputMode !== 'audio'" class="muted rate-current">当前生效：{{ model.projectVoiceRateLabel }}</div>
      </div>

      <div class="grid2 sceneMetaGrid voice-preview-grid">
        <div class="softItem">
          <div class="muted label-strong">当前将使用的配音配置</div>
          <div class="voice-config-list">
            <div v-if="model.inputMode === 'audio'">音频来源：复用上传主音频</div>
            <template v-else>
              <div>配音方式：{{ model.currentTtsBackendLabel }}</div>
              <div>当前音色：{{ model.currentTtsVoiceLabel }}</div>
              <div>项目语速：{{ model.projectVoiceRateLabel }}</div>
            </template>
          </div>
          <audio v-if="model.project?.voice_url" :src="model.project.voice_url" controls class="voice-audio" />
          <div v-else class="muted empty-top-gap">{{ model.inputMode === 'audio' ? '当前还没有绑定主音频。' : '当前还没有生成配音音频；生成时会使用上述配置。' }}</div>
        </div>

        <div class="softItem">
          <div class="muted label-strong">最终字幕预览</div>
          <div v-if="model.subtitlePreviewBusy" class="muted empty-top-gap">正在读取字幕文件…</div>
          <div v-else-if="model.subtitlePreviewText" class="script-preview preview-top-gap subtitle-preview">{{ model.subtitlePreviewText }}</div>
          <div v-else class="muted empty-top-gap">{{ model.subtitlePreviewErr || '当前还没有生成或上传字幕文件。' }}</div>
          <a v-if="model.project?.subtitle_url" class="btnGhost subtitle-link" :href="model.project.subtitle_url" target="_blank">打开字幕文件</a>
        </div>
      </div>

      <div class="softItem muted narration-box">
        <div class="narration-title">镜头旁白汇总</div>
        <div class="narration-content">{{ model.project ? narrationSummary(model.project) : '' }}</div>
      </div>
    </div>
  </StepPanel>
</template>

<style scoped>
.step-content-inner {
  padding: 20px;
}

.sceneMetaGrid {
  gap: 16px;
}

.voice-preview-grid {
  margin-top: 16px;
}

.rate-box {
  margin-bottom: 16px;
}

.rate-title {
  font-weight: 760;
  color: var(--ink);
}

.rate-copy {
  margin-top: 6px;
  line-height: 1.45;
}

.rate-current {
  margin-top: 10px;
}

.label-strong {
  font-weight: 760;
}

.voice-config-list {
  margin-top: 10px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  line-height: 1.45;
}

.voice-audio {
  width: 100%;
  margin-top: 10px;
}

.empty-top-gap {
  margin-top: 10px;
}

.preview-top-gap {
  margin-top: 10px;
}

.subtitle-preview {
  max-height: 240px;
  overflow: auto;
}

.subtitle-link {
  margin-top: 10px;
  display: inline-flex;
}

.narration-box {
  margin-top: 16px;
  line-height: 1.5;
  padding: 12px;
  background: rgba(0, 0, 0, 0.03);
  border-radius: 8px;
}

html.dark .narration-box {
  background: rgba(255, 255, 255, 0.03);
}

.narration-title {
  font-weight: 760;
  color: var(--ink);
}

.narration-content {
  margin-top: 8px;
  white-space: pre-wrap;
}

@media (max-width: 900px) {
  .grid2 {
    grid-template-columns: 1fr;
  }
}
</style>
