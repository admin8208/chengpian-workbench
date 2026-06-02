import { computed, type ComputedRef, type Ref } from 'vue'
import type { Asset, ProjectDetail, Scene } from '../../../api'

type MaterialMode = 'ai' | 'network'
type FlowStep = 'input' | 'storyboard' | 'voice' | 'media' | 'render'

function sceneRenderMeta(scene: Scene | null | undefined) {
  const meta = scene?.meta && typeof scene.meta === 'object' ? scene.meta : {}
  const render = meta && typeof (meta as any).render === 'object' ? (meta as any).render : {}
  return render && typeof render === 'object' ? render : {}
}

function sceneClipRange(scene: Scene | null | undefined): [number | null, number | null] {
  const render = sceneRenderMeta(scene)
  const start = render?.clip_start_sec
  const end = render?.clip_end_sec
  const startNum = typeof start === 'number' ? start : Number(start)
  const endNum = typeof end === 'number' ? end : Number(end)
  if (!Number.isFinite(startNum) || !Number.isFinite(endNum) || endNum <= startNum) return [null, null]
  return [startNum, endNum]
}

function clipOverlapRatio(left: [number | null, number | null], right: [number | null, number | null]): number {
  const [a0, a1] = left
  const [b0, b1] = right
  if (a0 == null || a1 == null || b0 == null || b1 == null) return 1
  const overlap = Math.max(0, Math.min(a1, b1) - Math.max(a0, b0))
  if (overlap <= 0) return 0
  const shorter = Math.max(1e-6, Math.min(a1 - a0, b1 - b0))
  return Math.max(0, Math.min(1, overlap / shorter))
}

export function useProjectSceneIssues(options: {
  project: Ref<ProjectDetail | null>
  selectedSceneId: Ref<number | null>
  selectedScene: ComputedRef<Scene | null>
  assetById: ComputedRef<Map<number, Asset>>
  materialMode: ComputedRef<MaterialMode>
  loadSuggestions: (scene: Scene) => Promise<void>
  goStep: (step: FlowStep, manual?: boolean) => void
}) {
  const { project, selectedSceneId, selectedScene, assetById, materialMode, loadSuggestions, goStep } = options

  function sceneAssetType(scene: Scene | null | undefined) {
    const aid = Number(scene?.image_asset_id || 0)
    if (!aid) return '无素材'
    const a = assetById.value.get(aid)
    if (!a) return '素材待加载'
    if (a.kind === 'video') return '视频素材'
    if (a.kind === 'image') return '图片素材'
    return '已绑定素材'
  }

  function sceneConfirmed(scene: Scene | null | undefined) {
    return Number(scene?.image_asset_id || 0) > 0
  }

  const duplicateSceneIds = computed(() => {
    const groups = new Map<number, Scene[]>()
    for (const scene of project.value?.scenes || []) {
      const aid = Number(scene.image_asset_id || 0)
      if (!aid) continue
      const rows = groups.get(aid) || []
      rows.push(scene)
      groups.set(aid, rows)
    }
    const duplicates = new Set<number>()
    for (const scenes of groups.values()) {
      if (scenes.length <= 1) continue
      const kinds = new Set(scenes.map((scene) => String(sceneRenderMeta(scene)?.asset_kind || '').trim().toLowerCase()).filter(Boolean))
      if (kinds.size > 0 && !kinds.has('video')) {
        scenes.forEach((scene) => duplicates.add(scene.id))
        continue
      }
      for (let i = 0; i < scenes.length; i += 1) {
        for (let j = i + 1; j < scenes.length; j += 1) {
          const left = scenes[i]
          const right = scenes[j]
          if (!left || !right) continue
          if (clipOverlapRatio(sceneClipRange(left), sceneClipRange(right)) >= 0.6) {
            duplicates.add(left.id)
            duplicates.add(right.id)
          }
        }
      }
    }
    return duplicates
  })

  function sceneIssueTags(scene: Scene | null | undefined) {
    const out: Array<{ key: string; label: string; tone: 'bad' | 'run' | 'ok' }> = []
    const aid = Number(scene?.image_asset_id || 0)
    if (!aid) out.push({ key: 'missing', label: materialMode.value === 'ai' ? '缺镜头图' : '缺素材', tone: 'bad' })
    if (aid && scene?.id && duplicateSceneIds.value.has(scene.id)) out.push({ key: 'duplicate', label: '重复素材', tone: 'run' })
    if (!out.length && sceneConfirmed(scene)) out.push({ key: 'confirmed', label: '已确认', tone: 'ok' })
    return out
  }

  const issueScenes = computed(() => {
    const priority: Record<string, number> = { missing: 0, duplicate: 1, confirmed: 9 }
    return (project.value?.scenes || [])
      .map((scene: Scene) => ({ scene, tags: sceneIssueTags(scene) }))
      .filter((item: { scene: Scene; tags: Array<{ key: string; label: string; tone: 'bad' | 'run' | 'ok' }> }) => item.tags.some((tag) => tag.key !== 'confirmed'))
      .sort((a: { scene: Scene; tags: Array<{ key: string; label: string; tone: 'bad' | 'run' | 'ok' }> }, b: { scene: Scene; tags: Array<{ key: string; label: string; tone: 'bad' | 'run' | 'ok' }> }) => {
        const ap = Math.min(...a.tags.map((tag: { key: string }) => priority[tag.key] ?? 8))
        const bp = Math.min(...b.tags.map((tag: { key: string }) => priority[tag.key] ?? 8))
        return ap - bp || a.scene.idx - b.scene.idx
      })
  })

  const sceneIssueStats = computed(() => {
    const stats = { missing: 0, duplicate: 0 }
    for (const scene of project.value?.scenes || []) {
      const tags = sceneIssueTags(scene)
      if (tags.some((tag) => tag.key === 'missing')) stats.missing += 1
      if (tags.some((tag) => tag.key === 'duplicate')) stats.duplicate += 1
    }
    return stats
  })

  function renderRiskSummary() {
    const stats = sceneIssueStats.value
    return `${materialMode.value === 'ai' ? '缺镜头图' : '缺素材'} ${stats.missing} · 重复素材 ${stats.duplicate}`
  }

  function hasRenderBlockingIssues() {
    const stats = sceneIssueStats.value
    return stats.missing > 0
  }

  function ensureRenderReady(actionLabel: string) {
    if (!hasRenderBlockingIssues()) return true
    const ok = confirm(`当前还有未修复镜头：\n${renderRiskSummary()}\n\n建议先修复问题镜头，再${actionLabel}。\n\n如果继续，成片可能出现错配素材或叙事断裂。\n\n是否仍然继续？`)
    return ok
  }

  const sceneQueue = computed(() => {
    const issueIds = new Set(issueScenes.value.map((item: { scene: Scene }) => item.scene.id))
    const rest = (project.value?.scenes || []).filter((scene: Scene) => !issueIds.has(scene.id))
    return [...issueScenes.value.map((item: { scene: Scene }) => item.scene), ...rest]
  })

  const selectedSceneTags = computed(() => sceneIssueTags(selectedScene.value))

  function focusSceneIssues(setInfo?: (message: string) => void) {
    goStep('media', true)
    if (!issueScenes.value.length) return
    const currentIndex = issueScenes.value.findIndex((item: { scene: Scene }) => item.scene.id === selectedSceneId.value)
    const nextIssue = issueScenes.value[currentIndex >= 0 && currentIndex + 1 < issueScenes.value.length ? currentIndex + 1 : 0]
    const bad = nextIssue?.scene || issueScenes.value[0]?.scene || null
    if (!bad) return
    const el = document.getElementById('scene-qc-panel')
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
    selectedSceneId.value = bad.id
    loadSuggestions(bad).catch(() => {
      setInfo?.('镜头建议加载失败，请稍后重试。')
    })
  }

  return {
    sceneAssetType,
    sceneIssueTags,
    issueScenes,
    sceneIssueStats,
    sceneQueue,
    selectedSceneTags,
    ensureRenderReady,
    focusSceneIssues,
  }
}
