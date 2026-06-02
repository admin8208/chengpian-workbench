<script setup lang="ts">
import { ElButton, ElInput, ElOption, ElSelect } from 'element-plus'

type ImageTestSize = '1024x1024' | '944x1664' | '1664x944'

type ImagePanelModel = {
  imageName: string
  imageModel: string
  imageBaseUrl: string
  imageKey: string
  imageSaving: boolean
  imageTesting: boolean
   imageQuickSummary: string
  imageTestSize: ImageTestSize
  imageTestSizeOptions: readonly ImageTestSize[]
  imageValidationPrompt: string
  imageTestResult: string
  saveImage: () => Promise<void>
  testImage: () => Promise<void>
}

defineProps<{
  busy: boolean
  showPlainSecrets: boolean
  model: ImagePanelModel
}>()
</script>

<template>
  <section class="card" style="padding: 20px">
    <div class="section-title">生图模型设置</div>
    <div class="softItem muted" style="margin-top: 8px; line-height: 1.45">{{ model.imageQuickSummary }}</div>
    <div class="softItem muted" style="margin-top: 10px; line-height: 1.5">点一次测试即可验证当前生图模型是否能真实出图。当前默认策略会按项目画幅优先尝试横版 1664x944 或竖版 944x1664，并在必要时回退到 1024x1024。</div>
    <div class="rowGrid" style="margin-top: 12px">
      <ElInput :model-value="model.imageName" placeholder="名称" @update:model-value="model.imageName = String($event || '')" />
      <ElInput :model-value="model.imageModel" placeholder="模型名" @update:model-value="model.imageModel = String($event || '')" />
    </div>
    <div class="rowGrid">
      <ElInput :model-value="model.imageBaseUrl" placeholder="接口地址" @update:model-value="model.imageBaseUrl = String($event || '')" />
      <ElInput :model-value="model.imageKey" :type="showPlainSecrets ? 'text' : 'password'" placeholder="接口密钥" @update:model-value="model.imageKey = String($event || '')" />
    </div>
    <div class="row" style="margin-top: 10px; gap: 8px">
      <ElButton type="primary" :disabled="model.imageSaving || busy" @click="model.saveImage">保存并设为默认</ElButton>
      <ElButton :disabled="model.imageTesting || busy" @click="model.testImage">测试生图模型</ElButton>
    </div>
    <div class="verifyGrid">
      <ElSelect
        :model-value="model.imageTestSize"
        placeholder="验证尺寸"
        @update:model-value="model.imageTestSize = (($event || '1664x944') as '1024x1024' | '944x1664' | '1664x944')"
      >
        <ElOption v-for="size in model.imageTestSizeOptions" :key="size" :label="size" :value="size" />
      </ElSelect>
      <ElInput
        :model-value="model.imageValidationPrompt"
        type="textarea"
        :rows="3"
        placeholder="用于真实尺寸验证的提示词"
        @update:model-value="model.imageValidationPrompt = String($event || '')"
      />
    </div>
    <div v-if="model.imageTestResult" class="muted" style="margin-top: 8px">{{ model.imageTestResult }}</div>
  </section>
</template>

<style scoped>
.rowGrid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-top: 10px;
}

.verifyGrid {
  display: grid;
  grid-template-columns: 220px minmax(0, 1fr);
  gap: 12px;
  margin-top: 14px;
}

@media (max-width: 980px) {
  .rowGrid {
    grid-template-columns: 1fr;
  }

  .verifyGrid {
    grid-template-columns: 1fr;
  }
}
</style>
