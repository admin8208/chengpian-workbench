<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElButton, ElEmpty, ElIcon, ElSkeleton, ElTabPane, ElTabs, ElUpload, ElDialog, ElForm, ElFormItem, ElInput, ElSelect, ElOption, ElBreadcrumb, ElBreadcrumbItem, ElTable, ElTableColumn, ElAlert, ElCheckbox } from 'element-plus'
import { UploadFilled, FolderOpened, Cloudy, Search, Delete } from '@element-plus/icons-vue'
import { useLibraryAssets } from './useLibraryAssets'
import { useCloudImport } from './useCloudImport'
import type { CloudFileItem } from '../../api/types'

const activeTab = ref('images')
const {
  loading,
  searchQuery,
  selectionMode,
  selectedAssetIds,
  batchDeleting,
  filteredAssets,
  allSelected,
  loadAssets,
  handleUpload,
  deleteAsset,
  handleTabChange,
  toggleSelectionMode,
  toggleSelect,
  selectAll,
  batchDelete,
  assetDisplayName,
} = useLibraryAssets(activeTab)

const {
  showCloudDialog,
  showCloudBrowser,
  cloudType,
  cloudConfig,
  cloudFiles,
  cloudLoading,
  cloudBreadcrumbs,
  selectedFile,
  openCloudDialog,
  getCloudFormTitle,
  testCloudConnection,
  navigateToPath,
  handleFileClick,
  importFromCloud,
  getFileIcon,
  formatFileSize,
  isOAuthType,
} = useCloudImport({ activeTab, loadAssets })

onMounted(() => {
  loadAssets()
})
</script>

<template>
  <div class="library-view">
    <section class="heroPanel card" style="margin-top: 16px; padding: 20px;">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
        <h2 class="section-title" style="margin-bottom: 0;">
          <ElIcon><FolderOpened /></ElIcon>
          素材库
        </h2>
        <div style="display: flex; gap: 12px;">
          <ElButton @click="openCloudDialog">
            <ElIcon class="el-icon--left"><Cloudy /></ElIcon>
            连接网盘
          </ElButton>
          <ElUpload
            :show-file-list="false"
            :http-request="handleUpload"
            :accept="activeTab === 'images' ? '.png,.jpg,.jpeg,.webp' : '.mp4,.mov,.mkv,.webm'"
          >
            <ElButton type="primary">
              <ElIcon class="el-icon--left"><UploadFilled /></ElIcon>
              上传素材
            </ElButton>
          </ElUpload>
        </div>
      </div>

      <div class="muted" style="margin-bottom: 16px; line-height: 1.6">
        管理你的公共素材库。上传的素材可以在创建项目时使用。支持从网盘导入素材。
      </div>
      <div class="softItem muted" style="margin-bottom: 16px; line-height: 1.45">
        这里是公共素材区。删除或替换素材会影响正在复用它的项目；WebDAV 连接仅支持公网可访问地址。
      </div>

      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
        <ElInput
          v-model="searchQuery"
          placeholder="搜索素材..."
          :prefix-icon="Search"
          clearable
          @input="loadAssets"
          style="max-width: 400px;"
        />
        <div style="display: flex; gap: 12px; align-items: center;">
          <ElButton :type="selectionMode ? 'warning' : 'default'" @click="toggleSelectionMode">
            {{ selectionMode ? '取消选择' : '批量选择' }}
          </ElButton>
          <template v-if="selectionMode">
            <ElButton @click="selectAll">
              {{ allSelected ? '取消全选' : '全选' }}
            </ElButton>
            <ElButton 
              type="danger" 
              :disabled="selectedAssetIds.length === 0"
              :loading="batchDeleting"
              @click="batchDelete"
            >
              <ElIcon class="el-icon--left"><Delete /></ElIcon>
              删除选中 ({{ selectedAssetIds.length }})
            </ElButton>
          </template>
        </div>
      </div>

      <ElTabs v-model="activeTab" @tab-change="handleTabChange">
        <ElTabPane label="图片素材" name="images" />
        <ElTabPane label="视频素材" name="videos" />
      </ElTabs>
    </section>

    <section class="card" style="margin-top: 16px; padding: 20px;">
      <ElSkeleton v-if="loading" :rows="4" animated />

      <template v-else>
        <ElEmpty v-if="filteredAssets.length === 0" description="暂无素材，点击上传或连接网盘导入">
          <div style="display: flex; gap: 12px;">
            <ElUpload
              :show-file-list="false"
              :http-request="handleUpload"
              :accept="activeTab === 'images' ? '.png,.jpg,.jpeg,.webp' : '.mp4,.mov,.mkv,.webm'"
            >
              <ElButton type="primary">上传素材</ElButton>
            </ElUpload>
            <ElButton @click="openCloudDialog">连接网盘</ElButton>
          </div>
        </ElEmpty>

        <div v-else class="asset-grid">
          <div 
            v-for="asset in filteredAssets" 
            :key="asset.id" 
            class="asset-card"
            :class="{ 'selected': selectionMode && selectedAssetIds.includes(asset.id) }"
            @click="selectionMode ? toggleSelect(asset.id) : null"
          >
            <div v-if="selectionMode" class="asset-checkbox">
              <ElCheckbox :model-value="selectedAssetIds.includes(asset.id)" @click.stop="toggleSelect(asset.id)" />
            </div>
            <div class="asset-preview">
              <img v-if="asset.kind === 'image'" :src="asset.url" :alt="assetDisplayName(asset)" />
              <video v-else :src="asset.url" muted />
            </div>
            <div class="asset-info">
              <div class="asset-name" :title="assetDisplayName(asset)">{{ assetDisplayName(asset) }}</div>
              <ElButton v-if="!selectionMode" size="small" type="danger" text @click.stop="deleteAsset(asset)">删除</ElButton>
            </div>
          </div>
        </div>
      </template>
    </section>

    <!-- 网盘连接对话框 -->
    <ElDialog v-model="showCloudDialog" :title="getCloudFormTitle()" width="500px">
      <ElForm label-width="100px">
        <ElFormItem label="网盘类型">
          <ElSelect v-model="cloudType" style="width: 100%;">
            <ElOption label="WebDAV (坚果云/NextCloud)" value="webdav" />
            <ElOption label="阿里云盘" value="aliyun" />
            <ElOption label="百度网盘" value="baidu" />
            <ElOption label="OneDrive" value="onedrive" />
          </ElSelect>
        </ElFormItem>
        
        <template v-if="cloudType === 'webdav'">
          <ElFormItem label="服务器地址">
            <ElInput v-model="cloudConfig.url" placeholder="https://dav.jianguoyun.com/dav/" />
          </ElFormItem>
          <ElFormItem label="用户名">
            <ElInput v-model="cloudConfig.username" placeholder="your@email.com" />
          </ElFormItem>
          <ElFormItem label="密码">
            <ElInput v-model="cloudConfig.password" type="password" placeholder="应用专用密码" />
          </ElFormItem>
        </template>
        
        <template v-if="isOAuthType(cloudType)">
          <ElAlert type="info" :closable="false" style="margin-bottom: 16px;">
            <template #title>
              <div style="font-size: 13px;">
                请先在对应网盘开放平台创建应用，获取授权后填入以下信息。
              </div>
            </template>
          </ElAlert>
          <ElFormItem label="访问令牌">
            <ElInput v-model="cloudConfig.access_token" placeholder="Access Token" />
          </ElFormItem>
          <ElFormItem label="刷新令牌">
            <ElInput v-model="cloudConfig.refresh_token" placeholder="Refresh Token (可选)" />
          </ElFormItem>
          <ElFormItem v-if="cloudType === 'onedrive'" label="Client ID">
            <ElInput v-model="cloudConfig.client_id" placeholder="应用 Client ID" />
          </ElFormItem>
          <ElFormItem v-if="cloudType === 'onedrive'" label="Client Secret">
            <ElInput v-model="cloudConfig.client_secret" type="password" placeholder="应用 Client Secret" />
          </ElFormItem>
        </template>
        
        <ElFormItem label="远程路径">
          <ElInput v-model="cloudConfig.path" placeholder="/" />
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="showCloudDialog = false">取消</ElButton>
        <ElButton type="primary" @click="testCloudConnection">连接</ElButton>
      </template>
    </ElDialog>

    <!-- 网盘文件浏览器 -->
    <ElDialog v-model="showCloudBrowser" title="网盘文件浏览器" width="800px" top="5vh">
      <div style="margin-bottom: 16px;">
        <ElBreadcrumb separator="/">
          <ElBreadcrumbItem v-for="(crumb, index) in cloudBreadcrumbs" :key="index">
            <span v-if="index === cloudBreadcrumbs.length - 1">{{ crumb }}</span>
            <a v-else @click="navigateToPath('/' + cloudBreadcrumbs.slice(1, index + 1).join('/') + '/')">{{ crumb }}</a>
          </ElBreadcrumbItem>
        </ElBreadcrumb>
      </div>

      <ElSkeleton v-if="cloudLoading" :rows="5" animated />

      <template v-else>
        <ElTable 
          :data="cloudFiles" 
          style="width: 100%" 
          @row-click="handleFileClick"
          highlight-current-row
          :row-class-name="({ row }: { row: CloudFileItem }) => selectedFile?.path === row.path ? 'selected-row' : ''"
        >
          <ElTableColumn label="名称" min-width="300">
            <template #default="{ row }">
              <div style="display: flex; align-items: center; gap: 8px;">
                <ElIcon :size="18"><component :is="getFileIcon(row)" /></ElIcon>
                <span>{{ row.name }}</span>
              </div>
            </template>
          </ElTableColumn>
          <ElTableColumn label="大小" width="100">
            <template #default="{ row }">
              {{ row.is_dir ? '-' : formatFileSize(row.size) }}
            </template>
          </ElTableColumn>
          <ElTableColumn label="操作" width="120">
            <template #default="{ row }">
              <ElButton v-if="!row.is_dir" size="small" type="primary" @click.stop="importFromCloud(row)">
                导入
              </ElButton>
              <span v-else style="color: var(--ink-soft); font-size: 12px;">双击打开</span>
            </template>
          </ElTableColumn>
        </ElTable>
        
        <div v-if="selectedFile" style="margin-top: 16px; padding: 12px; background: var(--el-fill-color-light); border-radius: 8px;">
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <div>
              <div style="font-weight: 500;">已选择: {{ selectedFile.name }}</div>
              <div style="font-size: 12px; color: var(--ink-soft);">{{ formatFileSize(selectedFile.size) }}</div>
            </div>
            <ElButton type="primary" @click="importFromCloud()">导入选中文件</ElButton>
          </div>
        </div>
      </template>
    </ElDialog>
  </div>
</template>

<style scoped>
.library-view {
  margin: 0 auto;
  padding: 0 16px;
}

.section-title {
  font-size: 18px;
  font-weight: 700;
  margin: 0 0 8px 0;
  color: var(--ink);
  line-height: 1.2;
  display: flex;
  align-items: center;
  gap: 8px;
}

.asset-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 16px;
}

.asset-card {
  border: 1px solid var(--line);
  border-radius: 10px;
  overflow: hidden;
  transition: all 0.25s ease;
  position: relative;
  cursor: default;
}

.asset-card.selection-mode {
  cursor: pointer;
}

.asset-card.selected {
  border-color: var(--el-color-primary);
  box-shadow: 0 0 0 2px var(--el-color-primary-light-5);
}

.asset-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.12);
}

.asset-checkbox {
  position: absolute;
  top: 8px;
  left: 8px;
  z-index: 10;
  background: white;
  border-radius: 4px;
  padding: 2px;
}

.asset-preview {
  width: 100%;
  height: 150px;
  overflow: hidden;
  background: #f5f5f5;
}

.asset-preview img,
.asset-preview video {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.asset-info {
  padding: 10px 12px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.asset-name {
  font-size: 13px;
  color: var(--ink);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
  margin-right: 8px;
}

:deep(.selected-row) {
  background-color: var(--el-color-primary-light-9) !important;
}
</style>
