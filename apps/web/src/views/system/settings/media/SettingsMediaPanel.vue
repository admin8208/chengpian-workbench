<script setup lang="ts">
import { ElButton, ElInput, ElOption, ElSelect } from 'element-plus'
import type { MediaProvider, WebMediaItem } from '../../../../api'
import type { RenderAspect } from '../../../../renderConfig'

type MediaPanelModel = {
  pexelsKey: string
  pixabayKey: string
  mediaSaving: boolean
   mediaQuickSummary: string
  mediaTestQuery: string
  mediaTestKind: 'video' | 'image'
  mediaTestAspect: RenderAspect
  mediaTestProvider: MediaProvider
  mediaTestItems: WebMediaItem[]
  mediaTestResult: string
  mediaTesting: boolean
  saveMediaKey: (provider: 'pexels' | 'pixabay', key: string) => Promise<void>
  runMediaTest: () => Promise<void>
}

defineProps<{
  busy: boolean
  showPlainSecrets: boolean
  model: MediaPanelModel
}>()
</script>

<template>
  <section class="card" style="padding: 20px">
    <div class="section-title">素材来源（联网搜索）</div>
    <div class="softItem muted" style="margin-top: 8px; line-height: 1.45">{{ model.mediaQuickSummary }}</div>
    <div class="rowGrid" style="margin-top: 12px">
      <div class="softItem muted">
        <div style="font-weight: 760">Pexels</div>
        <ElInput :model-value="model.pexelsKey" :type="showPlainSecrets ? 'text' : 'password'" placeholder="Pexels 接口密钥" style="margin-top: 8px" @update:model-value="model.pexelsKey = String($event || '')" />
        <ElButton type="primary" :disabled="model.mediaSaving || !model.pexelsKey.trim() || busy" style="margin-top: 8px" @click="model.saveMediaKey('pexels', model.pexelsKey)">保存</ElButton>
      </div>
      <div class="softItem muted">
        <div style="font-weight: 760">Pixabay</div>
        <ElInput :model-value="model.pixabayKey" :type="showPlainSecrets ? 'text' : 'password'" placeholder="Pixabay 接口密钥" style="margin-top: 8px" @update:model-value="model.pixabayKey = String($event || '')" />
        <ElButton type="primary" :disabled="model.mediaSaving || !model.pixabayKey.trim() || busy" style="margin-top: 8px" @click="model.saveMediaKey('pixabay', model.pixabayKey)">保存</ElButton>
      </div>
    </div>

    <div class="softItem" style="margin-top: 12px">
      <div style="font-weight: 760">测试参数</div>
      <div class="row" style="margin-top: 10px; gap: 8px; flex-wrap: wrap">
        <ElSelect :model-value="model.mediaTestProvider" style="max-width: 180px" @update:model-value="model.mediaTestProvider = $event === 'pexels' || $event === 'pixabay' ? $event : 'wikimedia'">
          <ElOption label="Wikimedia" value="wikimedia" />
          <ElOption label="Pexels" value="pexels" />
          <ElOption label="Pixabay" value="pixabay" />
        </ElSelect>
        <ElSelect :model-value="model.mediaTestKind" style="max-width: 140px" @update:model-value="model.mediaTestKind = $event === 'image' ? 'image' : 'video'">
          <ElOption label="视频" value="video" />
          <ElOption label="图片" value="image" />
        </ElSelect>
        <ElSelect :model-value="model.mediaTestAspect" style="max-width: 140px" @update:model-value="model.mediaTestAspect = $event === 'portrait' ? 'portrait' : 'landscape'">
          <ElOption label="横版" value="landscape" />
          <ElOption label="竖版" value="portrait" />
        </ElSelect>
        <ElInput :model-value="model.mediaTestQuery" placeholder="测试关键词" style="min-width: 320px; flex: 1 1 320px" @update:model-value="model.mediaTestQuery = String($event || '')" />
        <ElButton :disabled="model.mediaTesting || !model.mediaTestQuery.trim() || busy" @click="model.runMediaTest">测试连接</ElButton>
      </div>
      <div v-if="model.mediaTestResult" class="muted" style="margin-top: 8px">{{ model.mediaTestResult }}</div>
      <div v-if="model.mediaTestItems.length" class="mediaTestList" style="margin-top: 10px">
        <a v-for="item in model.mediaTestItems" :key="item.file_url" class="mediaTestItem" :href="item.page_url" target="_blank">
          <div style="font-weight: 760">{{ item.title || '未命名素材' }}</div>
          <div class="muted" style="margin-top: 4px">{{ item.kind }}<span v-if="item.width && item.height"> · {{ item.width }}×{{ item.height }}</span></div>
        </a>
      </div>
    </div>
  </section>
</template>

<style scoped>
.rowGrid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-top: 10px;
}

.mediaTestList {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.mediaTestItem {
  display: block;
  padding: 12px;
  border-radius: 12px;
  border: 1px solid var(--line);
  text-decoration: none;
}

@media (max-width: 980px) {
  .rowGrid,
  .mediaTestList {
    grid-template-columns: 1fr;
  }
}
</style>
