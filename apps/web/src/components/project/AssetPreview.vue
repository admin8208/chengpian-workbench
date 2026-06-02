<script setup lang="ts">
import { ref, computed } from 'vue'
import { ElIcon, ElButton, ElTooltip, ElDialog } from 'element-plus'
import { Download, ZoomIn } from '@element-plus/icons-vue'
import type { Asset } from '../../api'

interface Props {
  asset: Asset
  selected: boolean
}

const props = defineProps<Props>()
const emit = defineEmits<{
  'select-asset': [asset: Asset]
  'download-asset': [asset: Asset]
}>()

const showFullPreview = ref(false)
const isMuted = ref(true)

const assetType = computed(() => {
  return props.asset.kind || 'unknown'
})

const assetName = computed(() => {
  return String(props.asset.meta?.title || '').trim() || props.asset.url.split('/').pop() || '未命名素材'
})

const assetDuration = computed(() => {
  if (assetType.value === 'video' && props.asset.meta) {
    return Number(props.asset.meta.duration) || 0
  }
  return 0
})

const assetDimensions = computed(() => {
  if (props.asset.meta) {
    const width = Number(props.asset.meta.width) || 0
    const height = Number(props.asset.meta.height) || 0
    if (width && height) {
      return `${width}×${height}`
    }
  }
  return '未知尺寸'
})

function toggleMute() {
  isMuted.value = !isMuted.value
}

function selectAsset() {
  emit('select-asset', props.asset)
}

function downloadAsset() {
  emit('download-asset', props.asset)
}

function openFullPreview() {
  showFullPreview.value = true
}
</script>

<template>
  <div 
    class="asset-preview"
    :class="{ selected: selected }"
    @click="selectAsset"
  >
      <!-- 素材预览 -->
      <div class="preview-container">
      <video 
        v-if="assetType === 'video'" 
        :src="asset.url"
        :muted="isMuted"
        :autoplay="false"
        :controls="true"
        class="preview-video"
      />
      <img 
        v-else-if="assetType === 'image'" 
        :src="asset.url"
        class="preview-image"
        alt="素材预览图"
      />
        <div v-else class="preview-placeholder">
          <span class="placeholder-icon">{{ assetType === 'audio' ? '🎵' : '🖼' }}</span>
          <span>{{ assetType }}</span>
        </div>
      
      <!-- 预览控制 -->
      <div class="preview-controls">
        <ElTooltip content="下载素材">
          <ElButton 
            type="success" 
            circle 
            size="small"
            @click.stop="downloadAsset"
          >
            <ElIcon><Download /></ElIcon>
          </ElButton>
        </ElTooltip>
        <ElTooltip content="全屏预览">
          <ElButton 
            type="info" 
            circle 
            size="small"
            @click.stop="openFullPreview"
          >
            <ElIcon><ZoomIn /></ElIcon>
          </ElButton>
        </ElTooltip>
      </div>
    </div>
    
    <!-- 素材信息 -->
    <div class="asset-info">
      <div class="asset-name">{{ assetName }}</div>
      <div class="asset-meta">
        <span v-if="assetType === 'video'" class="meta-item">
          {{ assetDuration.toFixed(1) }}s
        </span>
        <span class="meta-item">{{ assetDimensions }}</span>
        <span class="meta-item">{{ assetType }}</span>
      </div>
    </div>
    
    <!-- 选择指示器 -->
    <div v-if="selected" class="selected-indicator">
      <ElIcon class="check-icon">✓</ElIcon>
    </div>
    
    <!-- 全屏预览对话框 -->
    <ElDialog 
      v-model="showFullPreview"
      :title="assetName"
      width="80%"
      top="10vh"
    >
      <div class="full-preview">
        <video 
          v-if="assetType === 'video'" 
          :src="asset.url"
          :muted="isMuted"
          :autoplay="true"
          :controls="true"
          class="full-preview-video"
        />
        <img 
          v-else-if="assetType === 'image'" 
          :src="asset.url"
          class="full-preview-image"
          alt="素材预览图"
        />
        <div v-else class="full-preview-placeholder">
          <span class="placeholder-icon">{{ assetType === 'audio' ? '🎵' : '🖼' }}</span>
          <span>{{ assetType }} 素材</span>
        </div>
        
        <div class="full-preview-info">
          <h3>{{ assetName }}</h3>
          <div class="meta-info">
            <span v-if="assetType === 'video'" class="meta-item">
              时长: {{ assetDuration.toFixed(1) }}秒
            </span>
            <span class="meta-item">
              尺寸: {{ assetDimensions }}
            </span>
            <span class="meta-item">
              类型: {{ assetType }}
            </span>
          </div>
          <div class="controls">
            <ElButton 
              v-if="assetType === 'video'"
              type="default" 
              @click="toggleMute"
            >
              {{ isMuted ? '取消静音' : '静音' }}
            </ElButton>
            <ElButton 
              type="primary"
              @click="downloadAsset"
            >
              <ElIcon><Download /></ElIcon>
              下载素材
            </ElButton>
          </div>
        </div>
      </div>
    </ElDialog>
  </div>
</template>

<style scoped>
.asset-preview {
  background: #f8f9fa;
  border-radius: 12px;
  padding: 12px;
  margin-bottom: 12px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
  transition: all 0.3s ease;
  cursor: pointer;
  position: relative;
  overflow: hidden;
}

.asset-preview:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  transform: translateY(-2px);
}

.asset-preview.selected {
  border: 2px solid #3b82f6;
  background: rgba(59, 130, 246, 0.05);
}

.preview-container {
  position: relative;
  width: 100%;
  height: 150px;
  border-radius: 8px;
  overflow: hidden;
  background: #e9ecef;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 12px;
}

.preview-video,
.preview-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.preview-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #6c757d;
}

.preview-placeholder ElIcon {
  font-size: 48px;
  margin-bottom: 8px;
}

.preview-controls {
  position: absolute;
  bottom: 8px;
  right: 8px;
  display: flex;
  gap: 4px;
  background: rgba(0, 0, 0, 0.6);
  padding: 4px;
  border-radius: 8px;
  opacity: 0;
  transition: opacity 0.3s ease;
}

.asset-preview:hover .preview-controls {
  opacity: 1;
}

.preview-controls .el-button {
  width: 28px;
  height: 28px;
  padding: 0;
}

.asset-info {
  min-width: 0;
}

.asset-name {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 4px;
  color: #343a40;
  display: -webkit-box;
  -webkit-line-clamp: 1;
  -webkit-box-orient: vertical;
  overflow: hidden;
  text-overflow: ellipsis;
}

.asset-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  font-size: 12px;
  color: #6c757d;
}

.meta-item {
  background: #e9ecef;
  padding: 2px 8px;
  border-radius: 12px;
}

.selected-indicator {
  position: absolute;
  top: 8px;
  left: 8px;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: #3b82f6;
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: bold;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
}

.full-preview {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.full-preview-video {
  width: 100%;
  height: 500px;
  object-fit: contain;
  background: #000;
  border-radius: 8px;
}

.full-preview-image {
  max-width: 100%;
  max-height: 500px;
  object-fit: contain;
  margin: 0 auto;
}

.full-preview-placeholder {
  width: 100%;
  height: 500px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: #e9ecef;
  border-radius: 8px;
  color: #6c757d;
}

.full-preview-placeholder ElIcon {
  font-size: 64px;
  margin-bottom: 16px;
}

.full-preview-info {
  text-align: center;
}

.full-preview-info h3 {
  margin-bottom: 8px;
  color: #343a40;
}

.meta-info {
  display: flex;
  justify-content: center;
  gap: 12px;
  margin-bottom: 16px;
  font-size: 14px;
  color: #6c757d;
}

.controls {
  display: flex;
  justify-content: center;
  gap: 12px;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .preview-container {
    height: 120px;
  }
  
  .full-preview-video {
    height: 300px;
  }
  
  .meta-info {
    flex-direction: column;
    gap: 4px;
  }
}
</style>
