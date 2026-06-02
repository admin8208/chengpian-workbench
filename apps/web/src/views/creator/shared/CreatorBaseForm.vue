<script setup lang="ts">
import { ElAlert, ElButton, ElInput, ElOption, ElSelect, ElTag } from 'element-plus'
import type { ChannelPack } from '../../../api'

type CreatorBaseFormModel = {
  title: string
  source: string
  selectedPack: string
  inputMode: 'text' | 'audio'
  materialMode: 'ai' | 'network'
  mediaPickMode: 'smart' | 'random_video'
  audioFileName: string
  creating: boolean
  err: string
  info: string
  packs: ChannelPack[]
  modeLabel: string
  modeHint: string
  heroTitle: string
  createButtonLabel: string
  setTitle: (value: string) => void
  setSource: (value: string) => void
  setSelectedPack: (value: string) => void
  setInputMode: (value: 'text' | 'audio') => void
  setMediaPickMode: (value: 'smart' | 'random_video') => void
  setAudioFile: (file: File | null) => void
  createProject: () => Promise<void>
  clearErr: () => void
  clearInfo: () => void
}

const props = defineProps<{ model: CreatorBaseFormModel }>()

function onAudioChange(event: Event) {
  const file = ((event.target as HTMLInputElement).files || [])[0] || null
  props.model.setAudioFile(file)
}
</script>

<template>
  <div style="display: flex; flex-direction: column; gap: 12px">
    <section class="heroPanel">
      <div class="heroInner" style="align-items: flex-start">
        <div>
          <div class="heroTitle" style="margin-top: 12px">{{ model.heroTitle }}</div>
          <div class="row" style="margin-top: 14px; gap: 8px; flex-wrap: wrap">
            <ElTag :type="model.modeLabel.includes('智能') ? 'success' : 'warning'">当前模式：{{ model.modeLabel }}</ElTag>
            <ElTag :type="model.inputMode === 'audio' ? 'danger' : 'info'">输入：{{ model.inputMode === 'audio' ? '音频驱动' : '文案驱动' }}</ElTag>
          </div>
        </div>
      </div>
      <ElAlert v-if="model.info" :title="model.info" type="success" show-icon closable @close="model.clearInfo" style="margin: 0 24px 12px" />
      <ElAlert v-if="model.err" :title="model.err" type="error" show-icon closable @close="model.clearErr" style="margin: 0 24px 18px" />
    </section>

    <section class="card">
      <div class="cardTitle">创建新项目</div>
      <div class="muted" style="margin-top: 10px">{{ model.modeHint }}</div>

      <div class="labelBlockTitle" style="margin-top: 18px">内容输入方式</div>
      <div class="row" style="margin-top: 16px; gap: 12px; flex-wrap: wrap">
        <div class="mode-card" :class="{ selected: model.inputMode === 'text' }" @click="model.setInputMode('text')">
          <div class="mode-title">文案驱动</div>
          <div class="mode-hint">从标题/原文生成脚本，再继续完成后续流程。</div>
        </div>
        <div class="mode-card" :class="{ selected: model.inputMode === 'audio' }" @click="model.setInputMode('audio')">
          <div class="mode-title">音频驱动</div>
          <div class="mode-hint">先上传旁白音频，系统转写后继续生成视频。</div>
        </div>
      </div>

      <template v-if="model.materialMode === 'network'">
        <div class="labelBlockTitle" style="margin-top: 18px">素材选择方式</div>
        <div class="row" style="margin-top: 16px; gap: 12px; flex-wrap: wrap">
          <div class="mode-card" :class="{ selected: model.mediaPickMode === 'smart' }" @click="model.setMediaPickMode('smart')">
            <div class="mode-title">智能匹配</div>
            <div class="mode-hint">根据文案和分镜关键词搜索、导入并绑定素材。</div>
          </div>
          <div class="mode-card" :class="{ selected: model.mediaPickMode === 'random_video' }" @click="model.setMediaPickMode('random_video')">
            <div class="mode-title">随机视频</div>
            <div class="mode-hint">素材阶段优先从素材库随机视频；素材库无视频时回退联网找视频。</div>
          </div>
        </div>
      </template>

      <div class="rowGrid" style="margin-top: 16px">
        <ElInput :model-value="model.title" placeholder="输入项目标题，例如：反向心理学开场" @update:model-value="model.setTitle(String($event || ''))" />
        <ElSelect :model-value="model.selectedPack" placeholder="选择赛道" @update:model-value="model.setSelectedPack(String($event || ''))">
          <ElOption v-for="p in model.packs" :key="p.key" :label="p.name" :value="p.key" />
        </ElSelect>
      </div>

      <ElInput
        v-if="model.inputMode === 'text'"
        :model-value="model.source"
        type="textarea"
        :rows="4"
        placeholder="可选：贴入原文。留空也可以，先创建项目，后续在项目页继续补充。"
        style="margin-top: 10px"
        @update:model-value="model.setSource(String($event || ''))"
      />

      <div v-else class="softItem muted" style="margin-top: 10px">
        <div style="font-weight: 760; margin-bottom: 8px">上传主音频</div>
        <input type="file" accept="audio/mp3,audio/wav,audio/m4a,audio/aac,.mp3,.wav,.m4a,.aac" @change="onAudioChange" />
        <div style="margin-top: 8px">{{ model.audioFileName || '请先选择一条旁白音频，后续会直接复用该音频。' }}</div>
      </div>

      <div class="row" style="margin-top: 12px; gap: 8px">
        <ElButton type="primary" :loading="model.creating" @click="model.createProject">{{ model.createButtonLabel }}</ElButton>
      </div>
    </section>
  </div>
</template>

<style scoped>
.mode-card {
  flex: 1;
  min-width: 220px;
  max-width: 320px;
  padding: 16px;
  border: 2px solid var(--line);
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.mode-card:hover {
  border-color: rgba(59, 130, 246, 0.3);
  background: rgba(59, 130, 246, 0.04);
}

.mode-card.selected {
  border-color: #1d4ed8;
  background: rgba(29, 78, 216, 0.08);
}

.mode-title {
  font-size: 15px;
  font-weight: 780;
  margin-bottom: 4px;
}

.labelBlockTitle {
  font-size: 13px;
  font-weight: 800;
  color: var(--ink);
}

.mode-hint {
  font-size: 12px;
  color: var(--ink-faint);
}
</style>
