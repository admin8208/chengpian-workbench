<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElAlert, ElButton } from 'element-plus'
import { api, type VideoToAudioResult } from '../../api'

const router = useRouter()
const selectedFile = ref<File | null>(null)
const converting = ref(false)
const creatingProject = ref(false)
const err = ref('')
const info = ref('')
const result = ref<VideoToAudioResult | null>(null)
const projectTitle = ref('')
const projectChannel = ref('emotion')
const materialMode = ref<'network' | 'ai'>('network')
const videoUrl = ref('')
const downloading = ref(false)

const fileLabel = computed(() => selectedFile.value?.name || '未选择视频文件')

function onPickFile(event: Event) {
  const input = event.target as HTMLInputElement
  selectedFile.value = (input.files || [])[0] || null
  result.value = null
  err.value = ''
  info.value = ''
}

async function convert() {
  if (converting.value || downloading.value) return
  if (!selectedFile.value) {
    err.value = '请先选择一个视频文件。'
    return
  }
  converting.value = true
  err.value = ''
  info.value = ''
  result.value = null
  try {
    result.value = await api.videoToAudio(selectedFile.value, 'mp3')
    info.value = '音频提取完成，可直接试听或下载。'
  } catch (e: any) {
    err.value = e?.message ?? String(e)
  } finally {
    converting.value = false
  }
}

async function downloadFromUrl() {
  if (converting.value || downloading.value) return
  const url = videoUrl.value.trim()
  if (!url) {
    err.value = '请先输入视频链接。'
    return
  }
  downloading.value = true
  err.value = ''
  info.value = ''
  result.value = null
  try {
    result.value = await api.videoUrlToAudio(url)
    info.value = '音频提取完成，可直接试听或下载。'
  } catch (e: any) {
    err.value = e?.message ?? String(e)
  } finally {
    downloading.value = false
  }
}

function formatSize(size: number) {
  const value = Number(size || 0)
  if (value <= 0) return '0 B'
  if (value < 1024) return `${value} B`
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`
  return `${(value / (1024 * 1024)).toFixed(2)} MB`
}

async function createAudioProject() {
  if (creatingProject.value) return
  if (!result.value) return
  creatingProject.value = true
  err.value = ''
  info.value = ''
  try {
    const channelLabels: Record<string, string> = {
      emotion: '情感关系',
      career: '职场成长',
      family_cn: '中式家庭',
      history: '历史悬疑',
    }
    const channelLabel = channelLabels[projectChannel.value] || '音频'
    const fileLabel = selectedFile.value?.name?.replace(/\.[^.]+$/, '') || ''
    const defaultTitle = fileLabel ? `${channelLabel}·${fileLabel}` : `${channelLabel}项目`
    
    const res = await api.createAudioProjectFromTool({
      title: projectTitle.value.trim() || defaultTitle,
      channel_key: projectChannel.value,
      material_mode: materialMode.value,
      rel_path: result.value.rel_path,
    })
    await router.push({ path: materialMode.value === 'ai' ? `/p/ai/${res.project_id}` : `/p/network/${res.project_id}` })
  } catch (e: any) {
    err.value = e?.message ?? String(e)
  } finally {
    creatingProject.value = false
  }
}
</script>

<template>
  <div style="display: flex; flex-direction: column; gap: 12px">
    <section class="heroPanel">
      <div class="heroInner" style="align-items: flex-start">
        <div>
          <div class="heroTitle" style="margin-top: 12px">视频转音频</div>
          <div class="muted" style="margin-top: 8px">上传本地视频，系统会自动提取音轨并输出标准 `mp3` 文件。</div>
        </div>
      </div>
      <ElAlert v-if="info" :title="info" type="success" show-icon closable @close="info = ''" style="margin: 0 24px 12px" />
      <ElAlert v-if="err" :title="err" type="error" show-icon closable @close="err = ''" style="margin: 0 24px 18px" />
    </section>

    <section class="card">
      <div class="cardTitle">提取音频</div>
      <div class="muted" style="margin-top: 10px">支持 `mp4 / mov / mkv / webm / avi / m4v`，统一导出 `mp3`。</div>

      <div class="softItem muted" style="margin-top: 16px">
        <div style="font-weight: 760; margin-bottom: 8px">选择本地视频</div>
        <input type="file" accept="video/mp4,video/quicktime,video/x-matroska,video/webm,video/x-msvideo,.mp4,.mov,.mkv,.webm,.avi,.m4v" @change="onPickFile" />
        <div style="margin-top: 8px">当前文件：{{ fileLabel }}</div>
      </div>

      <div class="row" style="margin-top: 14px; gap: 10px">
        <ElButton type="primary" :loading="converting" :disabled="downloading" @click="convert">开始提取音频</ElButton>
      </div>

      <div class="softItem muted" style="margin-top: 16px">
        <div style="font-weight: 760; margin-bottom: 8px">或从视频链接提取音频</div>
        <div class="muted" style="margin-bottom: 10px">支持抖音、快手、B站、YouTube等主流平台</div>
        <input v-model="videoUrl" class="input" placeholder="粘贴视频链接" style="margin-bottom: 10px" />
        <div class="row" style="gap: 10px">
          <ElButton type="primary" :loading="downloading" :disabled="converting" @click="downloadFromUrl">提取音频</ElButton>
        </div>
      </div>

      <div v-if="result" class="softItem" style="margin-top: 16px">
        <div style="font-weight: 760; margin-bottom: 10px">提取结果</div>
        <div class="muted">文件名：{{ result.filename }}</div>
        <div class="muted" style="margin-top: 4px">大小：{{ formatSize(result.size) }}</div>
        <audio :src="result.url" controls style="width: 100%; margin-top: 12px" />
        <div class="row" style="margin-top: 12px; gap: 10px">
          <a class="btnLink" :href="result.url" target="_blank" download>下载音频</a>
        </div>

        <div class="softItem muted" style="margin-top: 16px">
          <div style="font-weight: 760; margin-bottom: 8px">或直接创建音频驱动项目</div>
          <input v-model="projectTitle" class="input" placeholder="项目标题（可选）" style="margin-bottom: 10px" />
          <div class="row" style="gap: 10px; flex-wrap: wrap">
            <select v-model="projectChannel" class="input" style="max-width: 220px">
              <option value="emotion">情感关系</option>
              <option value="career">职场成长</option>
              <option value="family_cn">中式家庭</option>
              <option value="history">历史悬疑</option>
            </select>
            <select v-model="materialMode" class="input" style="max-width: 220px">
              <option value="network">素材模式</option>
              <option value="ai">智能生图模式</option>
            </select>
            <ElButton type="success" :loading="creatingProject" :disabled="creatingProject" @click="createAudioProject">创建音频驱动项目</ElButton>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.btnLink {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 36px;
  padding: 0 14px;
  border-radius: 10px;
  border: 1px solid var(--line);
  text-decoration: none;
  color: var(--ink);
  background: rgba(255, 255, 255, 0.68);
}

html.dark .btnLink {
  background: rgba(15, 23, 42, 0.68);
}
</style>
