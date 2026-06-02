<script setup lang="ts">
type JobStatusModel = {
  visibleJobBar: boolean
  currentStageLabel: string
  currentSubstageLabel: string
  statusLabel: string
  jobProgress: number
  jobMessage: string
  failedStageSummary: string
  failed: boolean
  canContinueAutopilot: boolean
  continueLabel: string
  showRerun: boolean
  jobNeedsLlm: boolean
  jobNeedsImage: boolean
  jobNeedsMedia: boolean
  jobNeedsTts: boolean
  runPrimary: () => Promise<void>
  rerun: () => Promise<void>
  retryCurrentJob: () => Promise<void>
  copyError: () => Promise<void>
  goSettings: (tab: 'llm' | 'image' | 'media' | 'tts') => void
}

defineProps<{
  model: JobStatusModel
}>()
</script>

<template>
  <div v-if="model.visibleJobBar" class="job-progress-bar">
    <div class="progress-info">
      <span class="progress-label">流程状态</span>
      <span class="progress-status">{{ model.currentStageLabel }} · {{ model.statusLabel }} · {{ model.jobProgress }}%</span>
    </div>
    <div v-if="model.currentSubstageLabel" class="progress-substage">当前步骤：{{ model.currentSubstageLabel }}</div>
    <div class="progress-track">
      <div class="progress-fill" :style="{ width: `${model.jobProgress}%` }"></div>
    </div>
    <div v-if="model.failed && model.failedStageSummary" class="failed-summary">失败发生在：{{ model.failedStageSummary }}</div>
    <div v-if="model.jobMessage" class="progress-message">{{ model.jobMessage }}</div>

    <div v-if="model.failed" class="error-actions">
      <button v-if="model.canContinueAutopilot" class="btn" @click="model.runPrimary()">{{ model.continueLabel }}</button>
      <button v-if="model.showRerun" class="btnGhost" @click="model.rerun()">重新开始</button>
      <button class="btnGhost" @click="model.retryCurrentJob()">重试当前任务</button>
      <button class="btnGhost" @click="model.copyError()">复制错误</button>
      <button v-if="model.jobNeedsLlm" class="btn" @click="model.goSettings('llm')">去设置（大模型）</button>
      <button v-if="model.jobNeedsImage" class="btn" @click="model.goSettings('image')">去设置（生图）</button>
      <button v-if="model.jobNeedsMedia" class="btn" @click="model.goSettings('media')">去设置（素材 API）</button>
      <button v-if="model.jobNeedsTts" class="btn" @click="model.goSettings('tts')">去设置（配音）</button>
    </div>
  </div>
</template>

<style scoped>
.job-progress-bar {
  padding: 16px;
  background: rgba(20, 184, 166, 0.06);
  border-radius: 16px;
  border: 1px solid rgba(20, 184, 166, 0.12);
  margin-bottom: 16px;
}

.progress-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  flex-wrap: wrap;
  gap: 8px;
}

.progress-label {
  font-size: 14px;
  font-weight: 700;
}

.progress-status {
  font-size: 13px;
  color: var(--ink-soft);
}

.progress-track {
  height: 8px;
  background: rgba(15, 23, 42, 0.06);
  border-radius: 4px;
  overflow: hidden;
}

.progress-substage {
  font-size: 12px;
  color: var(--ink-soft);
  margin-bottom: 8px;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, rgba(20, 184, 166, 0.95), rgba(37, 99, 235, 0.85));
  border-radius: 4px;
  transition: width 300ms ease;
}

.progress-message {
  font-size: 12px;
  color: var(--ink-soft);
  margin-top: 8px;
}

.failed-summary {
  margin-top: 10px;
  font-size: 12px;
  color: #b91c1c;
  font-weight: 600;
}

.error-actions {
  display: flex;
  gap: 8px;
  margin-top: 12px;
  flex-wrap: wrap;
}
</style>
