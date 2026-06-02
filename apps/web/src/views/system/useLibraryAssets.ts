import { computed, ref, type Ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '../../api'
import type { Asset } from '../../api/types'

export function assetDisplayName(asset: Asset) {
  const meta = asset.meta || {}
  const candidate = String(meta.title || meta.original_filename || meta.filename || meta.name || asset.url || '').trim()
  if (!candidate) return `asset_${asset.id}`
  const fromPath = candidate.split('/').pop() || candidate
  return fromPath.trim() || `asset_${asset.id}`
}

function assetSearchText(asset: Asset) {
  const metaText = JSON.stringify(asset.meta || {}).toLowerCase()
  return `${assetDisplayName(asset).toLowerCase()} ${metaText} ${String(asset.url || '').toLowerCase()}`
}

export function useLibraryAssets(activeTab: Ref<string>) {
  const loading = ref(false)
  const assets = ref<Asset[]>([])
  const searchQuery = ref('')
  const selectionMode = ref(false)
  const selectedAssetIds = ref<number[]>([])
  const batchDeleting = ref(false)

  const filteredAssets = computed(() => {
    if (!searchQuery.value) return assets.value
    const query = searchQuery.value.toLowerCase()
    return assets.value.filter((asset) => assetSearchText(asset).includes(query))
  })

  const allSelected = computed(() => filteredAssets.value.length > 0 && filteredAssets.value.every((asset) => selectedAssetIds.value.includes(asset.id)))

  async function loadAssets() {
    loading.value = true
    try {
      const kind = activeTab.value === 'images' ? 'image' : 'video'
      assets.value = await api.listLibraryAssets(kind, searchQuery.value, 100)
    } catch (e: any) {
      ElMessage.error(e?.message ?? String(e))
    } finally {
      loading.value = false
    }
  }

  async function handleUpload(options: any) {
    try {
      const kind = activeTab.value === 'images' ? 'image' : 'video'
      await api.uploadLibraryAsset(options.file, kind)
      ElMessage.success('上传成功')
      await loadAssets()
    } catch (e: any) {
      ElMessage.error(e?.message ?? String(e))
    }
  }

  async function deleteAsset(asset: Asset) {
    try {
      await ElMessageBox.confirm(
        `确定删除素材《${assetDisplayName(asset)}》？\n\n这会删除服务器上的公共素材文件，且可能影响正在复用该素材的项目。`,
        '删除素材确认',
        { type: 'warning' }
      )
    } catch {
      return
    }
    try {
      await api.deleteLibraryAsset(asset.id)
      ElMessage.success('删除成功')
      selectedAssetIds.value = selectedAssetIds.value.filter((id) => id !== asset.id)
      await loadAssets()
    } catch (e: any) {
      ElMessage.error(e?.message ?? String(e))
    }
  }

  function handleTabChange() {
    loadAssets()
  }

  function toggleSelectionMode() {
    selectionMode.value = !selectionMode.value
    if (!selectionMode.value) selectedAssetIds.value = []
  }

  function toggleSelect(assetId: number) {
    const index = selectedAssetIds.value.indexOf(assetId)
    if (index === -1) selectedAssetIds.value.push(assetId)
    else selectedAssetIds.value.splice(index, 1)
  }

  function selectAll() {
    if (allSelected.value) selectedAssetIds.value = []
    else selectedAssetIds.value = filteredAssets.value.map((asset) => asset.id)
  }

  async function batchDelete() {
    if (selectedAssetIds.value.length === 0) {
      ElMessage.warning('请先选择要删除的素材')
      return
    }
    const count = selectedAssetIds.value.length
    try {
      await ElMessageBox.confirm(`确定删除选中的 ${count} 个素材？此操作不可恢复。`, '批量删除确认', { type: 'warning' })
    } catch {
      return
    }

    batchDeleting.value = true
    let deletedCount = 0
    try {
      for (const id of selectedAssetIds.value) {
        try {
          await api.deleteLibraryAsset(id)
          deletedCount++
        } catch (e: any) {
          console.error(`删除素材 ${id} 失败:`, e)
        }
      }
      await loadAssets()
      selectedAssetIds.value = []
      selectionMode.value = false
      if (deletedCount === count) ElMessage.success(`成功删除 ${deletedCount} 个素材`)
      else ElMessage.warning(`删除完成，成功 ${deletedCount} 个，失败 ${count - deletedCount} 个`)
    } finally {
      batchDeleting.value = false
    }
  }

  return {
    loading,
    assets,
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
  }
}
