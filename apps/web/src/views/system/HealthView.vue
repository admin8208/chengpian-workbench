<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api, type Health, type HealthComponent } from '../../api'
import { formatTime } from '../../utils/dateTime'

const health = ref<Health | null>(null)
const err = ref('')
const loading = ref(true)
const refreshing = ref(false)
const lastCheckedAt = ref('')

function componentOf(key: string) {
  return health.value?.components?.[key] || null
}

const storageComp = computed(() => componentOf('storage'))
const runtimePermComp = computed(() => componentOf('runtime_permissions'))
const workerComp = computed(() => componentOf('worker'))
const ffmpegComp = computed(() => componentOf('ffmpeg'))
const edgeComp = computed(() => componentOf('edge_tts'))
const offlineComp = computed(() => componentOf('offline_tts'))
const onlineBaseComp = computed(() => componentOf('online_base'))

const canRenderNow = computed(() => Boolean(storageComp.value?.ok && workerComp.value?.ok && ffmpegComp.value?.ok && (offlineComp.value?.ok || edgeComp.value?.ok)))
const renderRiskCount = computed(() => {
  let count = 0
  if (!storageComp.value?.ok) count += 1
  if (!runtimePermComp.value?.ok) count += 1
  if (!workerComp.value?.ok) count += 1
  if (!ffmpegComp.value?.ok) count += 1
  if (!offlineComp.value?.ok && !edgeComp.value?.ok) count += 1
  return count
})

const summaryTitle = computed(() => (canRenderNow.value ? '可以直接出片' : '需要先处理'))

function essentialTone(comp: HealthComponent | null) {
  return comp?.ok ? 'ok' : 'bad'
}

const essentialCards = computed(() => [
  {
    key: 'storage',
    title: '磁盘空间',
    tone: essentialTone(storageComp.value),
    badge: storageComp.value?.ok ? '不阻塞出片' : '需要先处理',
    summary: storageComp.value?.ok ? '用于保存素材、历史预览和最终成片。' : '如果这里异常，项目文件可能无法正常写入。',
    impact: '影响素材、历史预览和最终成片保存',
    status: storageComp.value?.status || '未检测',
    detail: storageComp.value?.detail || '',
    hint: storageComp.value?.hint || '',
  },
  {
    key: 'runtime_permissions',
    title: '运行目录权限',
    tone: essentialTone(runtimePermComp.value),
    badge: runtimePermComp.value?.ok ? '目录属主一致' : '需要先处理',
    summary: runtimePermComp.value?.ok ? '当前运行目录由同一服务用户维护，不容易出现删不掉或误创建 root 目录的问题。' : '检测到 data/ 运行区存在非 chengpian 属主条目，后续可能出现项目目录删不干净或服务无法写入。',
    impact: '影响项目目录创建、删除和导出写入',
    status: runtimePermComp.value?.status || '未检测',
    detail: runtimePermComp.value?.detail || '',
    hint: runtimePermComp.value?.hint || '',
  },
  {
    key: 'worker',
    title: '任务 Worker',
    tone: essentialTone(workerComp.value),
    badge: workerComp.value?.ok ? '任务可推进' : '会阻塞队列',
    summary: workerComp.value?.ok ? '负责消费队列里的任务，把排队中的项目真正推进到运行中。' : '如果 worker 离线，项目会长期停在排队中，无法真正开始执行。',
    impact: '影响 queued 任务是否能进入 running',
    status: workerComp.value?.status || '未检测',
    detail: workerComp.value?.detail || '',
    hint: workerComp.value?.hint || '',
  },
  {
    key: 'ffmpeg',
    title: '视频引擎',
    tone: essentialTone(ffmpegComp.value),
    badge: ffmpegComp.value?.ok ? '可渲染成片' : '会阻塞渲染',
    summary: ffmpegComp.value?.ok ? '负责合成视频轨、字幕和最终成片。' : 'ffmpeg 异常时，生成视频会卡在渲染阶段。',
    impact: '影响视频轨和最终成片渲染',
    status: ffmpegComp.value?.status || '未检测',
    detail: ffmpegComp.value?.detail || '',
    hint: ffmpegComp.value?.hint || '',
  },
  {
    key: 'offline_tts',
    title: '本地配音（推荐）',
    tone: essentialTone(offlineComp.value),
    badge: offlineComp.value?.ok ? '推荐路径可用' : '建议先安装',
    summary: offlineComp.value?.ok ? '这是当前最稳的出片路径，弱网环境也能继续生成。' : '如果在线配音不稳定，离线配音是最稳的主路径。',
    impact: '影响默认配音稳定性',
    status: offlineComp.value?.status || '未检测',
    detail: offlineComp.value?.detail || '',
    hint: offlineComp.value?.hint || '',
  },
  {
    key: 'edge_tts',
    title: '在线配音',
    tone: essentialTone(edgeComp.value),
    badge: edgeComp.value?.ok ? '可用' : '不可用',
    summary: edgeComp.value?.ok ? '在线配音可用，可作为离线配音的备选方案。' : '在线配音不可用，建议使用离线配音。',
    impact: '影响配音生成方式',
    status: edgeComp.value?.status || '未检测',
    detail: edgeComp.value?.detail || (onlineBaseComp.value && !onlineBaseComp.value.ok ? `网络诊断：${onlineBaseComp.value.detail || '无法访问微软服务'}` : ''),
    hint: edgeComp.value?.hint || '',
  },
])

async function load(options?: { silent?: boolean, probe?: boolean }) {
  err.value = ''
  if (!options?.silent) loading.value = true
  else refreshing.value = true
  try {
    health.value = await api.health({ probe: options?.probe })
    lastCheckedAt.value = formatTime(new Date())
  } catch (e: any) {
    err.value = e?.message ?? String(e)
  } finally {
    loading.value = false
    refreshing.value = false
  }
}

function retryLoad() {
  load().catch((e) => (err.value = e?.message ?? String(e)))
}

onMounted(() => {
  retryLoad()
})
</script>

<template>
  <div>
    <section class="heroPanel card" style="margin-top: 16px; padding: 20px;">
      <h2 class="section-title">出片前检查</h2>
      
      <!-- 状态指标 -->
      <div class="status-grid">
        <div class="status-card" :class="{ 'status-ok': canRenderNow, 'status-bad': !canRenderNow }">
          <div class="status-label">当前结论</div>
          <div class="status-value">{{ summaryTitle }}</div>
        </div>
        <div class="status-card" :class="{ 'status-bad': renderRiskCount > 0 }">
          <div class="status-label">阻塞项</div>
          <div class="status-value">{{ renderRiskCount }}</div>
        </div>
        <div class="status-card status-action-card">
          <div class="status-label">刷新检查</div>
          <button class="btn status-action-btn" :disabled="refreshing || loading" @click="load({ silent: true, probe: true })">{{ refreshing ? '刷新中…' : '刷新检查' }}</button>
          <div class="muted refresh-meta">上次刷新：{{ lastCheckedAt || '刚打开' }}</div>
        </div>
      </div>

      <div v-if="err" class="err" style="margin-top: 16px">{{ err }}</div>
    </section>

    <section v-if="loading && !health" class="card" style="margin-top: 16px">
      <div class="cardTitle">正在检查基础环境…</div>
      <div class="muted" style="margin-top: 8px">系统正在自动检测当前环境是否可以直接出片，以及在线配音是否可用。</div>
    </section>

    <section v-else-if="err && !health" class="card" style="margin-top: 16px">
      <div class="cardTitle">健康检查加载失败</div>
      <div class="err" style="margin-top: 8px">{{ err }}</div>
      <div class="row" style="margin-top: 12px; flex-wrap: wrap">
        <button class="btn" @click="retryLoad">重试</button>
      </div>
    </section>

    <template v-else>
    <section class="card" style="margin-top: 16px; padding: 20px;">
        <h2 class="section-title">会直接影响出片的项目</h2>
        <div class="muted" style="margin-top: 8px; line-height: 1.5">只要这几项正常，你通常就能继续生成视频。</div>
        <div class="grid2">
          <div v-for="card in essentialCards" :key="card.key" class="item" :class="card.tone">
            <div class="card-header" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px">
              <div style="display: flex; align-items: center; gap: 12px">
                <div class="status-indicator" :class="card.tone"></div>
                <h3 style="font-size: 16px; font-weight: 700; margin: 0">{{ card.title }}</h3>
              </div>
              <div class="pill" :class="card.tone">{{ card.badge }}</div>
            </div>
            <div class="muted" style="margin-bottom: 12px; line-height: 1.5">{{ card.summary }}</div>
            <div class="softItem muted" style="margin-bottom: 12px">影响：{{ card.impact }}</div>
            <div class="statusLine">当前状态：{{ card.status }}</div>
            <div v-if="card.detail" class="techDetail">{{ card.detail }}</div>
            <div v-if="card.hint" class="muted" style="margin-top: 8px; margin-bottom: 12px">建议：{{ card.hint }}</div>
          </div>
        </div>
      </section>

    </template>
  </div>
</template>

<style scoped>
.grid2 {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 12px;
  margin-top: 12px;
}

.status-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.refresh-meta {
  margin-top: 10px;
  font-size: 12px;
}

.status-action-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.status-action-btn {
  margin-top: 8px;
}

.status-card {
  background: #ffffff;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 16px;
  text-align: center;
  transition: all 0.3s ease;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
}

.status-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.12);
}

.status-card.status-ok {
  border-color: rgba(16, 185, 129, 0.2);
  background: rgba(16, 185, 129, 0.05);
}

.status-card.status-bad {
  border-color: rgba(239, 68, 68, 0.2);
  background: rgba(239, 68, 68, 0.05);
}

.status-label {
  font-size: 14px;
  color: var(--ink-soft);
  margin-bottom: 4px;
}

.status-value {
  font-size: 20px;
  font-weight: 700;
  color: var(--ink);
}

.section-title {
  font-size: 18px;
  font-weight: 700;
  margin: 0 0 8px 0;
  color: var(--ink);
  line-height: 1.2;
}

.item {
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 12px;
  background: #ffffff;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
  transition: all 0.3s ease;
  display: flex;
  flex-direction: column;
  height: 100%;
}

.item:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.12);
}

.item.ok {
  border-color: rgba(16, 185, 129, 0.2);
  background: rgba(16, 185, 129, 0.05);
}

.item.bad {
  border-color: rgba(239, 68, 68, 0.2);
  background: rgba(239, 68, 68, 0.05);
}

.status-indicator {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}

.status-indicator.ok {
  background-color: #10b981;
  box-shadow: 0 0 0 4px rgba(16, 185, 129, 0.1);
}

.status-indicator.bad {
  background-color: #ef4444;
  box-shadow: 0 0 0 4px rgba(239, 68, 68, 0.1);
}

.statusLine {
  margin-top: 10px;
  font-size: 13px;
  color: var(--ink-soft);
}

.techDetail {
  margin-top: 8px;
  padding: 12px 14px;
  border-radius: 8px;
  border: 1px solid rgba(15, 23, 42, 0.08);
  background: rgba(15, 23, 42, 0.03);
  font-size: 13px;
  white-space: pre-wrap;
  line-height: 1.4;
}

@media (max-width: 768px) {
  .grid2 {
    grid-template-columns: 1fr !important;
  }
  
  .card {
    padding: 16px !important;
  }
}

/* 按钮样式优化 */
button {
  font: inherit;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 10px 16px;
  background: #3b82f6;
  color: white;
  cursor: pointer;
  font-weight: 500;
  transition: all 0.2s ease;
  box-shadow: 0 1px 3px rgba(59, 130, 246, 0.2);
}

button:hover {
  background: #2563eb;
  transform: translateY(-1px);
  box-shadow: 0 2px 6px rgba(59, 130, 246, 0.3);
}

button:disabled {
  background: #94a3b8;
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}

</style>
