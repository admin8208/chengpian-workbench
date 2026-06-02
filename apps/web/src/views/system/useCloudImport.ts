import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Document, Folder, Picture, VideoPlay } from '@element-plus/icons-vue'
import { api } from '../../api'
import type { CloudFileItem } from '../../api/types'

export function useCloudImport(options: { activeTab: { value: string }, loadAssets: () => Promise<void> }) {
  const { activeTab, loadAssets } = options
  const showCloudDialog = ref(false)
  const showCloudBrowser = ref(false)
  const cloudType = ref('webdav')
  const cloudConfig = ref({
    url: '',
    username: '',
    password: '',
    access_token: '',
    refresh_token: '',
    client_id: '',
    client_secret: '',
    path: '/',
  })
  const cloudFiles = ref<CloudFileItem[]>([])
  const cloudLoading = ref(false)
  const currentCloudPath = ref('/')
  const cloudBreadcrumbs = ref<string[]>([])
  const selectedFile = ref<CloudFileItem | null>(null)

  function openCloudDialog() {
    showCloudDialog.value = true
  }

  function getCloudFormTitle() {
    const titles: Record<string, string> = {
      webdav: 'WebDAV (坚果云/NextCloud)',
      aliyun: '阿里云盘',
      baidu: '百度网盘',
      onedrive: 'OneDrive',
    }
    return titles[cloudType.value] || '连接网盘'
  }

  async function testCloudConnection() {
    try {
      const result = await api.testConnection(cloudType.value, cloudConfig.value)
      if (result.success) {
        ElMessage.success(result.message)
        showCloudDialog.value = false
        showCloudBrowser.value = true
        const initialPath = String(cloudConfig.value.path || '/').trim() || '/'
        await loadCloudFiles(initialPath.startsWith('/') ? initialPath : `/${initialPath}`)
      } else {
        ElMessage.error(result.message)
      }
    } catch (e: any) {
      ElMessage.error(e?.message ?? String(e))
    }
  }

  function updateBreadcrumbs(path: string) {
    const parts = path.split('/').filter((part) => part)
    cloudBreadcrumbs.value = ['根目录', ...parts]
  }

  async function loadCloudFiles(path: string) {
    cloudLoading.value = true
    try {
      const result = await api.listFiles(cloudType.value, cloudConfig.value, path)
      cloudFiles.value = result.files
      currentCloudPath.value = result.current_path
      updateBreadcrumbs(result.current_path)
    } catch (e: any) {
      ElMessage.error(e?.message ?? String(e))
    } finally {
      cloudLoading.value = false
    }
  }

  function navigateToPath(path: string) {
    loadCloudFiles(path)
  }

  function handleFileClick(file: CloudFileItem) {
    if (file.is_dir) navigateToPath(file.path)
    else selectedFile.value = file
  }

  async function importFromCloud(file?: CloudFileItem) {
    const targetFile = file || selectedFile.value
    if (!targetFile) {
      ElMessage.warning('请先选择要导入的文件')
      return
    }
    try {
      const kind = activeTab.value === 'images' ? 'image' : 'video'
      const fileType = String(targetFile.type || '').trim().toLowerCase()
      if (fileType && fileType !== kind) {
        ElMessage.error(kind === 'image' ? '当前图片素材页只允许导入图片文件' : '当前视频素材页只允许导入视频文件')
        return
      }
      const fileId = String(targetFile.file_id || targetFile.id || targetFile.fs_id || '').trim()
      const result = await api.importFile(cloudType.value, cloudConfig.value, targetFile.path, fileId, kind)
      if (result.success) {
        ElMessage.success(result.message)
        selectedFile.value = null
        await loadAssets()
      } else {
        ElMessage.error(result.message)
      }
    } catch (e: any) {
      ElMessage.error(e?.message ?? String(e))
    }
  }

  function getFileIcon(file: CloudFileItem) {
    if (file.is_dir) return Folder
    if (file.type === 'image') return Picture
    if (file.type === 'video') return VideoPlay
    return Document
  }

  function formatFileSize(size: number) {
    if (size < 1024) return `${size} B`
    if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
    if (size < 1024 * 1024 * 1024) return `${(size / (1024 * 1024)).toFixed(1)} MB`
    return `${(size / (1024 * 1024 * 1024)).toFixed(1)} GB`
  }

  function isOAuthType(type: string) {
    return ['aliyun', 'baidu', 'onedrive'].includes(type)
  }

  return {
    showCloudDialog,
    showCloudBrowser,
    cloudType,
    cloudConfig,
    cloudFiles,
    cloudLoading,
    currentCloudPath,
    cloudBreadcrumbs,
    selectedFile,
    openCloudDialog,
    getCloudFormTitle,
    testCloudConnection,
    loadCloudFiles,
    navigateToPath,
    handleFileClick,
    importFromCloud,
    getFileIcon,
    formatFileSize,
    isOAuthType,
  }
}
