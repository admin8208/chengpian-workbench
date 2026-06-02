<script setup lang="ts">
import StepPanel from './StepPanel.vue'

type StepStatus = 'error' | 'running' | 'active' | 'pending' | 'completed'

type InputStepModel = {
  inputMode?: 'text' | 'audio'
  projectVoiceUrl?: string | null
  hasConfirmedBaseline?: boolean
  titleInput: string
  sourceInput: string
  autosaving: boolean
  generatedScript: string
  isGeneratingScript: boolean
  busy?: boolean
  primaryLabel?: string
  rerunLabel?: string
  canConfirmScript?: boolean
  runPrimary?: () => Promise<void>
  rerunScript?: () => Promise<void>
  saveProjectScript: (value: string) => Promise<void>
  confirmScriptAndRunAutopilot: () => Promise<void>
  uploadProjectVoice: (file: File) => Promise<void>
}

defineProps<{
  currentStep: string
  autoStep: string
  stepStatus: StepStatus
  isCompleted: boolean
  model: InputStepModel
}>()
</script>

<template>
  <StepPanel
    v-if="currentStep === 'input'"
    title="文案确认"
    :desc="model.inputMode === 'audio' ? '当前项目由上传音频驱动；系统会先转写出可编辑文案，待你确认后，再自动生成分镜、画面并复用该音频进入成片。' : '先生成可编辑的口播文案草稿，待你确认后，系统才会继续自动生成分镜、素材、字幕与成片。'"
    step-key="input"
    :is-active="currentStep === 'input'"
    :is-completed="isCompleted"
    :is-current="autoStep === 'input'"
    :status="stepStatus"
    :default-expanded="true"
  >
    <div class="step-content-inner">
      <div class="form-group">
        <label class="muted label-strong">主题一句话</label>
        <input class="input" :value="model.titleInput" placeholder="主题一句话…" @input="model.titleInput = ($event.target as HTMLInputElement).value" />
        <div v-if="model.autosaving" class="muted saving-text">正在保存…</div>
      </div>

      <div v-if="model.inputMode === 'audio'" class="softItem muted" style="margin-top: 12px">
        <div class="label-strong">当前主音频</div>
        <audio v-if="model.projectVoiceUrl" :src="model.projectVoiceUrl" controls style="width: 100%; margin-top: 10px" />
        <div v-else style="margin-top: 10px">当前还没有上传主音频。音频驱动模式下，系统会先基于主音频做转写分段，再进入脚本分镜和画面准备阶段。</div>
        <input
          type="file"
          accept="audio/mp3,audio/wav,audio/m4a,audio/aac,.mp3,.wav,.m4a,.aac"
          style="margin-top: 10px"
          @change="(($event.target as HTMLInputElement).files || [])[0] && model.uploadProjectVoice((($event.target as HTMLInputElement).files || [])[0] as File)"
        />
      </div>

      <details v-if="model.inputMode !== 'audio'" class="source-details">
        <summary class="muted source-summary">可选：粘贴原文/要点（更准）</summary>
        <textarea
          class="ta"
          :value="model.sourceInput"
          placeholder="粘贴原文、讲稿、笔记…（可为空）"
          style="margin-top: 10px"
          @input="model.sourceInput = ($event.target as HTMLTextAreaElement).value"
        />
      </details>

      <div class="script-block">
        <div class="row script-head">
          <label class="muted label-strong">项目口播脚本</label>
          <div v-if="model.hasConfirmedBaseline" class="pill ok">已确认</div>
          <div v-else-if="model.generatedScript" class="pill ok">待确认</div>
          <div v-else-if="model.isGeneratingScript" class="pill run">生成中</div>
        </div>

        <textarea
          v-if="model.generatedScript"
          class="ta script-top-gap"
          :value="model.generatedScript"
          rows="8"
          placeholder="这里会显示当前文案基线或转写结果"
          @input="model.saveProjectScript(($event.target as HTMLTextAreaElement).value)"
        />
        <div v-if="model.generatedScript" class="row" style="margin-top: 10px; justify-content: space-between; gap: 12px; flex-wrap: wrap">
          <div class="muted script-text">{{ model.hasConfirmedBaseline ? '当前文案已确认；如果继续修改，会自动回到待确认状态。' : '确认后的文案会作为分镜、素材、字幕和成片的统一基线。' }}</div>
          <div v-if="!model.hasConfirmedBaseline" class="row" style="gap: 8px; flex-wrap: wrap">
            <button v-if="model.rerunScript" class="btnGhost" type="button" :disabled="model.busy || model.isGeneratingScript" @click="model.rerunScript">{{ model.rerunLabel || (model.inputMode === 'audio' ? '重新识别转写' : '重新生成文案') }}</button>
            <button v-if="model.canConfirmScript" class="btn" type="button" :disabled="model.busy || model.isGeneratingScript" @click="model.confirmScriptAndRunAutopilot">确认文案</button>
          </div>
        </div>
        <div v-else-if="model.isGeneratingScript" class="softItem muted script-top-gap script-text">
          正在生成项目脚本，完成后这里会先显示整段口播基线；后面的镜头旁白、字幕和配音会参考这套脚本推进。
        </div>
        <div v-else class="softItem script-top-gap script-empty-state">
          <div class="muted script-text">
            这里展示的是项目当前脚本文案基线。先生成草稿，确认之后，系统才会继续自动生成分镜、画面、字幕和成片。
          </div>
          <button class="btn" type="button" :disabled="model.busy || model.isGeneratingScript || !model.runPrimary" @click="model.runPrimary?.()">
            {{ model.primaryLabel || (model.inputMode === 'audio' ? '识别转写' : '生成文案') }}
          </button>
        </div>
      </div>
    </div>
  </StepPanel>
</template>

<style scoped>
.step-content-inner {
  padding: 20px;
}

.form-group {
  margin-bottom: 16px;
}

.label-strong {
  font-weight: 760;
}

.saving-text {
  margin-top: 6px;
}

.source-details {
  margin-top: 12px;
}

.source-summary {
  cursor: pointer;
  font-weight: 820;
}

.script-block {
  margin-top: 16px;
}

.script-head {
  justify-content: space-between;
  gap: 12px;
}

.script-top-gap {
  margin-top: 10px;
}

.script-text {
  line-height: 1.5;
}

.script-empty-state {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.ta {
  width: 100%;
  min-height: 120px;
  padding: 12px;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.68);
  font-size: 14px;
  line-height: 1.6;
  resize: vertical;
  box-sizing: border-box;
  font-family: inherit;
}

html.dark .ta {
  background: rgba(30, 41, 59, 0.68);
}

.ta:focus {
  outline: none;
  border-color: var(--brand);
  box-shadow: 0 0 0 2px var(--ring);
}
</style>
