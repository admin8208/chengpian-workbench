<script setup lang="ts">
import { ElButton, ElInput, ElOption, ElSelect } from 'element-plus'

type LlmPanelModel = {
  llmName: string
  llmType: 'openai_compat' | 'ollama'
  llmBaseUrl: string
  llmModel: string
  llmKey: string
  llmSaving: boolean
  llmTesting: boolean
  llmTestResult: string
   llmQuickSummary: string
  saveLlm: () => Promise<void>
  testLlm: () => Promise<void>
}

defineProps<{
  busy: boolean
  showPlainSecrets: boolean
  model: LlmPanelModel
}>()
</script>

<template>
  <section class="card" style="padding: 20px">
    <div class="section-title">大模型设置</div>
    <div class="softItem muted" style="margin-top: 8px; line-height: 1.45">{{ model.llmQuickSummary }}</div>
    <div class="rowGrid" style="margin-top: 12px">
      <ElInput :model-value="model.llmName" placeholder="名称" @update:model-value="model.llmName = String($event || '')" />
      <ElSelect :model-value="model.llmType" @update:model-value="model.llmType = $event === 'ollama' ? 'ollama' : 'openai_compat'">
        <ElOption label="OpenAI 兼容" value="openai_compat" />
        <ElOption label="Ollama 本地" value="ollama" />
      </ElSelect>
    </div>
    <div class="rowGrid">
      <ElInput :model-value="model.llmBaseUrl" placeholder="服务地址，如 https://api.openai.com 或 http://127.0.0.1:11434" @update:model-value="model.llmBaseUrl = String($event || '')" />
      <ElInput :model-value="model.llmModel" placeholder="模型名" @update:model-value="model.llmModel = String($event || '')" />
    </div>
    <div class="muted" style="margin-top: 8px; line-height: 1.45">这里只填服务根地址或带 <code>/v1</code> 的地址，不要填写完整的 <code>/chat/completions</code>、<code>/images/generations</code> 或 <code>/models</code> 路径。保存时系统会自动规范化。</div>
    <div v-if="model.llmType === 'openai_compat'" class="rowGrid">
      <ElInput :model-value="model.llmKey" :type="showPlainSecrets ? 'text' : 'password'" placeholder="接口密钥" @update:model-value="model.llmKey = String($event || '')" />
    </div>
    <div class="row" style="margin-top: 10px; gap: 8px">
      <ElButton type="primary" :disabled="model.llmSaving || busy" @click="model.saveLlm">保存并设为默认</ElButton>
      <ElButton :disabled="model.llmTesting || busy" @click="model.testLlm">测试连接</ElButton>
    </div>
    <div v-if="model.llmTestResult" class="muted" style="margin-top: 8px">{{ model.llmTestResult }}</div>
  </section>
</template>

<style scoped>
.rowGrid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-top: 10px;
}

@media (max-width: 980px) {
  .rowGrid {
    grid-template-columns: 1fr;
  }
}
</style>
