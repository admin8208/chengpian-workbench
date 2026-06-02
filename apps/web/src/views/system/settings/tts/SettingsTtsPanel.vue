<script setup lang="ts">
import { ElButton, ElInput, ElOption, ElSelect } from 'element-plus'

type VoiceOption = {
  value: string
  label: string
  note?: string
  installed?: boolean
}

type TtsPanelModel = {
  ttsLoading: boolean
  ttsBackend: string
  offlineVoiceId: string
  edgeVoiceId: string
  defaultVoiceRate: string
  showAllEdgeVoices: boolean
  ttsInstallRunning: boolean
  cleanupInfo: string
  ttsPreviewText: string
  voiceRateOptions: readonly string[]
  ttsPreviewBusy: boolean
  ttsPreviewUrl: string
  ttsPreviewMode: 'offline_piper' | 'edge'
  ttsQuickSummary: string
  ttsBackendLabel: string
  installedOfflineVoices: unknown[]
  availableEdgeVoices: unknown[]
  visibleEdgeVoices: unknown[]
  incompatibleOfflineVoices: unknown[]
  offlineVoiceOptions: VoiceOption[]
  edgeVoiceOptions: VoiceOption[]
  previewModeLabel: string
  saveTtsBackend: () => Promise<void>
  reloadTtsStatus: () => Promise<void>
  previewCurrentTts: (mode?: 'offline_piper' | 'edge') => Promise<void>
  installOfflineTts: () => Promise<void>
  cleanupIncompatibleVoices: () => Promise<void>
}

defineProps<{
  busy: boolean
  model: TtsPanelModel
}>()
</script>

<template>
  <section class="card" style="padding: 20px">
    <div class="section-title">配音设置</div>
    <div class="softItem muted" style="margin-top: 8px; line-height: 1.45">{{ model.ttsQuickSummary }}</div>

    <div class="panelBlock">
      <div class="blockTitle">配音方式</div>
      <div class="row" style="margin-top: 10px; gap: 8px; flex-wrap: wrap">
        <ElSelect :model-value="model.ttsBackend" style="max-width: 260px" @update:model-value="model.ttsBackend = String($event || 'offline_piper')">
          <ElOption label="本机配音（稳定，无需联网）" value="offline_piper" />
          <ElOption label="自动选择（优先在线）" value="auto" />
          <ElOption label="在线配音（音色更自然）" value="edge" />
        </ElSelect>
        <ElSelect v-if="model.ttsBackend !== 'edge'" :model-value="model.offlineVoiceId" style="max-width: 320px" placeholder="选择本机离线音色" @update:model-value="model.offlineVoiceId = String($event || '')">
          <ElOption v-for="voice in model.offlineVoiceOptions" :key="voice.value" :label="`${voice.label}${voice.installed ? '（已安装）' : ''} · ${voice.note}`" :value="voice.value" />
        </ElSelect>
        <ElSelect v-if="model.ttsBackend !== 'offline_piper'" :model-value="model.edgeVoiceId" style="max-width: 420px" placeholder="选择微软在线音色" filterable @update:model-value="model.edgeVoiceId = String($event || '')">
          <ElOption v-for="voice in model.edgeVoiceOptions" :key="voice.value" :label="`${voice.label}${voice.note ? ` · ${voice.note}` : ''}`" :value="voice.value" />
        </ElSelect>
        <ElSelect :model-value="model.defaultVoiceRate" style="width: 150px" @update:model-value="model.defaultVoiceRate = String($event || '+0%')">
          <ElOption v-for="rate in model.voiceRateOptions" :key="rate" :label="rate === '+0%' ? '默认语速：正常' : `默认语速 ${rate}`" :value="rate" />
        </ElSelect>
        <ElButton :disabled="busy" @click="model.saveTtsBackend">保存</ElButton>
        <ElButton :disabled="busy || model.ttsLoading" @click="model.reloadTtsStatus">刷新状态</ElButton>
      </div>
      <label v-if="model.ttsBackend !== 'offline_piper'" class="muted edge-toggle">
        <input :checked="model.showAllEdgeVoices" type="checkbox" @change="model.showAllEdgeVoices = ($event.target as HTMLInputElement).checked" /> 显示全部在线音色（当前默认只显示 zh-CN 6 个）
      </label>
      <div v-if="model.ttsBackend !== 'offline_piper'" class="muted" style="margin-top: 6px">在线音色：当前显示 {{ model.visibleEdgeVoices.length }} 个，总计 {{ model.availableEdgeVoices.length }} 个。</div>
      <div class="muted" style="margin-top: 8px">当前选择：{{ model.ttsBackendLabel }} · 默认语速 {{ model.defaultVoiceRate === '+0%' ? '正常' : model.defaultVoiceRate }}</div>
    </div>

    <div class="panelBlock">
      <div class="blockTitle">本机配音安装</div>
      <div class="row" style="margin-top: 10px; gap: 8px; flex-wrap: wrap">
        <ElButton :disabled="busy || model.ttsInstallRunning" @click="model.installOfflineTts">{{ model.ttsInstallRunning ? '安装中…' : '安装全部兼容中文音色' }}</ElButton>
        <ElButton :disabled="busy" @click="model.cleanupIncompatibleVoices">清理不可用音色</ElButton>
      </div>
      <div v-if="model.cleanupInfo" class="muted" style="margin-top: 8px">{{ model.cleanupInfo }}</div>
      <div class="muted" style="margin-top: 10px">当前已安装 {{ model.installedOfflineVoices.length }} 个本机离线音色，可直接在上面的选择框里切换。</div>
      <div v-if="model.incompatibleOfflineVoices.length" class="muted" style="margin-top: 8px">当前发现 {{ model.incompatibleOfflineVoices.length }} 个不兼容音色，批量安装时会自动跳过。</div>
    </div>

    <div class="panelBlock">
      <div class="blockTitle">试听音色</div>
      <div class="muted" style="margin-top: 6px; line-height: 1.45">你可以分别试听本机配音和在线配音，直接听出差异。本机试听会使用当前本机音色，在线试听会使用上面选中的在线音色；试听语速会跟随上面保存的默认语速。</div>
      <div class="row" style="margin-top: 10px; gap: 8px; flex-wrap: wrap">
        <ElInput :model-value="model.ttsPreviewText" placeholder="输入一段试听文案" style="min-width: 360px; flex: 1 1 360px" @update:model-value="model.ttsPreviewText = String($event || '')" />
        <ElButton :disabled="model.ttsPreviewBusy || !model.ttsPreviewText.trim()" @click="model.previewCurrentTts('offline_piper')">{{ model.ttsPreviewBusy && model.ttsPreviewMode === 'offline_piper' ? '本机试听生成中…' : '试听本机配音' }}</ElButton>
        <ElButton :disabled="model.ttsPreviewBusy || !model.ttsPreviewText.trim()" @click="model.previewCurrentTts('edge')">{{ model.ttsPreviewBusy && model.ttsPreviewMode === 'edge' ? '在线试听生成中…' : '试听在线配音' }}</ElButton>
        <a v-if="model.ttsPreviewUrl" class="btnGhost" :href="model.ttsPreviewUrl" target="_blank">打开试听音频</a>
      </div>
      <div v-if="model.ttsPreviewUrl" class="muted" style="margin-top: 8px">当前结果：{{ model.previewModeLabel }} · 语速 {{ model.defaultVoiceRate === '+0%' ? '正常' : model.defaultVoiceRate }}</div>
    </div>
  </section>
</template>

<style scoped>
.panelBlock {
  margin-top: 18px;
  padding-top: 18px;
  border-top: 1px solid var(--line);
}

.blockTitle {
  font-weight: 760;
}

.edge-toggle {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-top: 8px;
}
</style>
