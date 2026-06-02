<script setup lang="ts">
import type { Asset } from '../../api'
import SectionIntro from '../shared/SectionIntro.vue'

const props = defineProps<{
  selectedVideoUrl: string
  finalExists: boolean
  finalVideoUrl: string
  exportVideos: Asset[]
  selectedVideoAsset: Asset | null
}>()

const emit = defineEmits<{
  'update:selectedVideoUrl': [value: string]
}>()

function assetMeta(a: Asset | null | undefined) {
  const meta = a?.meta
  return meta && typeof meta === 'object' ? meta : {}
}

function resolutionLabel(a: Asset) {
  const meta = assetMeta(a)
  const width = Number(meta.width || 0)
  const height = Number(meta.height || 0)
  return width > 0 && height > 0 ? `${width}×${height}` : '自动尺寸'
}

function subtitleLabel(a: Asset) {
  const meta = assetMeta(a)
  const mode = String(meta.subtitle_mode || '').trim().toLowerCase()
  if (mode === 'burned' || mode === 'burned_retry') return '已包含字幕'
  if (mode === 'audio_only') return '字幕已降级'
  return '字幕状态未知'
}

</script>

<template>
  <section class="videoStage">
    <div class="row" style="justify-content: space-between; align-items: start; gap: 12px">
      <div>
        <SectionIntro title="成片预览" desc="查看最终成片结果。" />
      </div>
      <a v-if="props.finalExists && props.finalVideoUrl" class="btnGhost" :href="props.finalVideoUrl" target="_blank">打开成片</a>
    </div>

    <div v-if="props.selectedVideoAsset" class="row" style="margin-top: 12px">
      <div class="pill">{{ resolutionLabel(props.selectedVideoAsset) }}</div>
      <div class="pill" :class="String(assetMeta(props.selectedVideoAsset).subtitle_mode || '') === 'audio_only' ? 'bad' : 'ok'">{{ subtitleLabel(props.selectedVideoAsset) }}</div>
    </div>

    <div v-if="!props.selectedVideoUrl" class="emptyState muted" style="margin-top: 14px; line-height: 1.5">
      还没有可预览的视频。请先运行"生成视频"。
      <div v-if="!props.finalExists" style="margin-top: 6px">当前项目还没有合法的最终成片记录。</div>
    </div>
    <div v-else class="videoShell">
      <video class="video" :src="props.selectedVideoUrl" controls playsinline />
    </div>
  </section>
</template>

<style scoped>
.videoStage {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.pill {
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
  background: rgba(0, 0, 0, 0.06);
  color: var(--ink-soft);
}

.pill.ok {
  background: rgba(34, 197, 94, 0.12);
  color: #16a34a;
}

.pill.run {
  background: rgba(245, 158, 11, 0.12);
  color: #d97706;
}

.pill.bad {
  background: rgba(239, 68, 68, 0.12);
  color: #dc2626;
}

.videoShell {
  margin-top: 12px;
  border-radius: 12px;
  overflow: hidden;
  background: #000;
}

.video {
  width: 100%;
  display: block;
}

.emptyState {
  text-align: center;
  padding: 40px 20px;
}

.btnGhost {
  padding: 8px 16px;
  border-radius: 8px;
  border: 1px solid var(--line);
  background: transparent;
  color: var(--ink);
  cursor: pointer;
  text-decoration: none;
  font-size: 14px;
}

.btnGhost:hover {
  background: rgba(0, 0, 0, 0.04);
}
</style>
