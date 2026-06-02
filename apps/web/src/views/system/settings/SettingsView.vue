<script setup lang="ts">
import { ElAlert, ElTabPane, ElTabs } from 'element-plus'
import { type SettingsTab, useSettingsView } from './useSettingsView'
import SettingsLlmPanel from './llm/SettingsLlmPanel.vue'
import SettingsImagePanel from './image/SettingsImagePanel.vue'
import SettingsMediaPanel from './media/SettingsMediaPanel.vue'
import SettingsTtsPanel from './tts/SettingsTtsPanel.vue'
import SettingsAccountPanel from './account/SettingsAccountPanel.vue'

const {
  tab,
  busy,
  info,
  err,
  showPlainSecrets,
  llm,
  image,
  media,
  tts,
  accounts,
  authStatus,
  isAdmin,
  llmSetupState,
  imageSetupState,
  mediaSetupState,
  ttsSetupState,
  setTab,
  setupStateLabel,
} = useSettingsView()
</script>

<template>
  <div style="display: flex; flex-direction: column; gap: 12px">
    <section class="heroPanel card" style="margin-top: 16px; padding: 20px">
      <div class="section-title">系统设置</div>
      <div class="muted" style="margin-top: 8px; line-height: 1.5">先把文案大模型、生图模型、联网素材来源和离线配音配好，后面的“生成视频”会顺很多。</div>
      <div class="softItem muted" style="margin-top: 12px; line-height: 1.45">这里的模型、素材来源和配音设置属于全局配置。修改后会影响后续所有项目与任务，不只是当前页面。</div>

      <div class="row" style="margin-top: 16px; gap: 8px; flex-wrap: wrap">
        <div class="pill" :class="{ ok: llmSetupState === 'ready', bad: llmSetupState === 'missing' }">大模型 {{ setupStateLabel(llmSetupState) }}</div>
        <div class="pill" :class="{ ok: imageSetupState === 'ready', bad: imageSetupState === 'missing' }">生图 {{ setupStateLabel(imageSetupState) }}</div>
        <div class="pill" :class="{ ok: mediaSetupState === 'ready', bad: mediaSetupState === 'missing' }">素材 {{ setupStateLabel(mediaSetupState) }}</div>
        <div class="pill" :class="{ ok: ttsSetupState === 'ready', bad: ttsSetupState === 'missing' }">配音 {{ setupStateLabel(ttsSetupState) }}</div>
      </div>

      <div class="softItem muted" style="margin-top: 14px; line-height: 1.45">
        <div>大模型：{{ llm.llmQuickSummary }}</div>
        <div style="margin-top: 6px">生图模型：{{ image.imageQuickSummary }}</div>
        <div style="margin-top: 6px">素材来源：{{ media.mediaQuickSummary }}</div>
        <div style="margin-top: 6px">配音：{{ tts.ttsQuickSummary }}</div>
      </div>

      <div style="margin-top: 14px">
        <ElTabs v-model="tab" @tab-click="(pane) => setTab(pane.paneName as SettingsTab)">
          <ElTabPane label="大模型" name="llm" />
          <ElTabPane label="生图模型" name="image" />
          <ElTabPane label="素材来源" name="media" />
          <ElTabPane label="配音" name="tts" />
          <ElTabPane v-if="isAdmin" label="账号" name="account" />
        </ElTabs>
      </div>

      <ElAlert v-if="info" type="success" :title="info" show-icon closable @close="info = ''" style="margin-top: 16px" />
      <ElAlert v-if="err" type="error" :title="err" show-icon closable @close="err = ''" style="margin-top: 16px" />
    </section>

    <SettingsLlmPanel
      v-if="tab === 'llm'"
      :busy="busy"
      :show-plain-secrets="showPlainSecrets"
      :model="llm"
    />

    <SettingsImagePanel
      v-if="tab === 'image'"
      :busy="busy"
      :show-plain-secrets="showPlainSecrets"
      :model="image"
    />

    <SettingsMediaPanel
      v-if="tab === 'media'"
      :busy="busy"
      :show-plain-secrets="showPlainSecrets"
      :model="media"
    />

    <SettingsTtsPanel
      v-if="tab === 'tts'"
      :busy="busy"
      :model="tts"
    />

    <SettingsAccountPanel
      v-if="tab === 'account' && isAdmin"
      :auth-username="authStatus?.username || '管理员'"
      :show-plain-secrets="showPlainSecrets"
      :model="accounts"
    />
  </div>
</template>
