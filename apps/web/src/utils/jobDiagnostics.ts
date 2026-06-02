import { labelAutopilotStage, labelJobFlowStage, labelJobSubstage, labelRenderSubstage, labelStage } from '../labels'
import type { Job } from '../api/index'
import type { JobDiagnosticsConfig } from './jobDiagnosticsConfig'

export type FlowStageView = {
  key: 'storyboard' | 'media' | 'tts' | 'render'
  label: string
  status: 'completed' | 'current' | 'pending' | 'failed'
  substeps: Array<{
    key: string
    label: string
    status: 'completed' | 'current' | 'pending' | 'failed'
  }>
}

export type JobChain = {
  rootId: number
  nodes: Job[]
  head: Job
}

const hiddenKinds = new Set(['tts_offline_install', 'tts_offline_install_all_compatible'])

export function isHiddenJobKind(kind: string | null | undefined) {
  return hiddenKinds.has(String(kind || '').trim())
}

export function jobRootId(j: Job) {
  const rid = Number(j.root_job_id || 0)
  return rid > 0 ? rid : Number(j.id)
}

export function buildJobChains(rows: Job[], options: { sortBy?: 'updated_at' | 'status' | 'progress' } = {}): JobChain[] {
  const sortBy = options.sortBy || 'updated_at'
  const groups = new Map<number, Job[]>()
  for (const j of rows) {
    if (isHiddenJobKind(j.kind)) continue
    const rid = jobRootId(j)
    const arr = groups.get(rid) || []
    arr.push(j)
    groups.set(rid, arr)
  }
  const out: JobChain[] = []
  for (const [rootId, arr] of groups.entries()) {
    const nodes = [...arr].sort((a, b) => {
      const ta = Date.parse(String(a.updated_at || '')) || 0
      const tb = Date.parse(String(b.updated_at || '')) || 0
      if (tb !== ta) return tb - ta
      return Number(b.id || 0) - Number(a.id || 0)
    })
    const active = nodes.find((x) => ['queued', 'running', 'paused'].includes(String(x.status || '').trim().toLowerCase()))
    const head = active || nodes[0]
    if (!head) continue
    out.push({ rootId, nodes, head })
  }

  out.sort((a, b) => {
    switch (sortBy) {
      case 'status': {
        const statusOrder = { running: 0, queued: 1, paused: 2, done: 3, failed: 4, cancelled: 5 }
        return (statusOrder[a.head.status as keyof typeof statusOrder] || 999) - (statusOrder[b.head.status as keyof typeof statusOrder] || 999)
      }
      case 'progress':
        return Number(b.head.progress || 0) - Number(a.head.progress || 0)
      case 'updated_at':
      default: {
        const ta = Date.parse(String(a.head.updated_at || '')) || 0
        const tb = Date.parse(String(b.head.updated_at || '')) || 0
        return tb - ta
      }
    }
  })

  return out
}

export function chainAttemptsLabel(c: JobChain) {
  const attempts = c.nodes.length
  if (attempts <= 1) return ''
  return `断点续传 ${attempts - 1} 次（共 ${attempts} 条记录）`
}

export function autopilotExecutionLabel(j: Job) {
  const payload: any = parseJobPayload(j)
  const retrySeq = Math.max(0, Number(j.retry_seq || 0))
  const resumeStage = String(payload.resume_from_stage || '').trim().toLowerCase()
  const renderSubstage = String(payload.render_substage || '').trim().toLowerCase()
  const message = String(j.message || '').trim()

  if (message === '重新开始') return retrySeq > 0 ? `第 ${retrySeq + 1} 次执行 · 重新开始` : '重新开始'

  if (resumeStage) {
    const stage = labelAutopilotStage(resumeStage, resumeStage)
    const sub = resumeStage === 'render' ? labelRenderSubstage(renderSubstage, '') : ''
    const suffix = [stage, sub].filter(Boolean).join(' / ')
    return retrySeq > 0 ? `第 ${retrySeq + 1} 次执行 · 从${suffix}继续` : `从${suffix}继续`
  }

  if (retrySeq > 0) return `第 ${retrySeq + 1} 次执行`
  return '首次执行'
}

export function autopilotChainSummary(c: JobChain) {
  if (!c.nodes.length) return ''
  if (c.nodes.length === 1) return autopilotExecutionLabel(c.head)
  return `${autopilotExecutionLabel(c.head)} · 本链路 ${c.nodes.length} 条记录`
}

export function recommendedAction(j: Job) {
  return String(j.recommended_action || '').trim().toLowerCase()
}

export function blockingComponent(j: Job) {
  return String(j.blocking_component || '').trim().toLowerCase()
}

export function needsLlm(j: Job) {
  return blockingComponent(j) === 'llm' || recommendedAction(j) === 'go_settings_llm'
}

export function needsMedia(j: Job) {
  return blockingComponent(j) === 'media' || recommendedAction(j) === 'go_settings_media'
}

export function needsTts(j: Job) {
  return blockingComponent(j) === 'tts' || recommendedAction(j) === 'go_settings_tts'
}

export function parseJobPayload(j: Job) {
  try {
    const obj = JSON.parse(String(j.payload_json || '{}'))
    return obj && typeof obj === 'object' ? obj : {}
  } catch {
    return {}
  }
}

function normalizedStage(j: Job) {
  const kind = String(j.kind || '').trim().toLowerCase()
  const payload: any = parseJobPayload(j)
  const direct = String(j.current_stage || '').trim().toLowerCase()
  const payloadStage = String(payload.current_stage || payload.last_failed_stage || '').trim().toLowerCase()
  if (kind === 'render') return 'render'
  return direct || payloadStage
}

function normalizedRenderSubstage(j: Job) {
  const payload: any = parseJobPayload(j)
  const direct = String(j.render_substage || '').trim().toLowerCase()
  const payloadSubstage = String(payload.render_substage || '').trim().toLowerCase()
  return direct || payloadSubstage
}

function normalizedSubstage(j: Job) {
  const kind = String(j.kind || '').trim().toLowerCase()
  if (kind === 'render') return ''
  const payload: any = parseJobPayload(j)
  const direct = String(j.current_substage || '').trim().toLowerCase()
  const payloadSubstage = String(payload.current_substage || '').trim().toLowerCase()
  return direct || payloadSubstage
}

function resolveConfig(materialMode?: string | JobDiagnosticsConfig | null): JobDiagnosticsConfig | null {
  return materialMode && typeof materialMode !== 'string' ? materialMode : null
}

function messageSubstage(j: Job, materialMode?: string | JobDiagnosticsConfig | null) {
  const msg = String(j.message || '').trim()
  const low = msg.toLowerCase()
  const config = resolveConfig(materialMode)
  const stage = normalizedStage(j)
  if (stage === 'storyboard') {
    if (msg.includes('合规')) return 'compliance'
    if (msg.includes('保存')) return 'save_storyboard'
    if (msg.includes('脚本') || msg.includes('分镜')) return 'generate_storyboard'
    return 'storyboard_running'
  }
  if (stage === 'media') {
    return config ? config.inferMediaSubstage(msg) : 'media_running'
  }
  if (stage === 'tts') {
    if (msg.includes('重建字幕') || msg.includes('自动重建字幕') || msg.includes('修复字幕')) return 'repair_subtitles'
    if (msg.includes('静音音轨')) return 'silent_voice_fallback'
    if (msg.includes('字幕')) return 'generate_subtitles'
    if (msg.includes('配音')) return 'generate_voice'
    if (low.includes('reuse') || msg.includes('复用')) return 'reuse_tts'
    return 'tts_running'
  }
  return ''
}

export function substageLabel(j: Job, materialMode?: string | JobDiagnosticsConfig | null) {
  const stage = normalizedStage(j)
  if (stage === 'render') {
    return labelRenderSubstage(normalizedRenderSubstage(j), normalizedRenderSubstage(j) ? '渲染处理中' : '')
  }
  const sub = normalizedSubstage(j) || messageSubstage(j, materialMode)
  if (stage === 'storyboard') {
    return labelJobSubstage(sub, '脚本分镜处理中')
  }
  if (stage === 'media') {
    return labelJobSubstage(sub, '画面准备处理中')
  }
  if (stage === 'tts') {
    return labelJobSubstage(sub, '配音字幕处理中')
  }
  return labelJobSubstage(sub, '')
}

export function mainStageLabel(j: Job) {
  const kind = String(j.kind || '').trim().toLowerCase()
  const stage = normalizedStage(j)
  if (stage) return labelStage(stage, kind === 'autopilot' ? '自动生成视频' : stageLabel(j))
  if (kind === 'images' || kind === 'scene_image' || kind === 'autofill_media') return '画面准备'
  if (kind === 'render') return '最终成片'
  return stageLabel(j)
}

export function stageSummary(j: Job, materialMode?: string | JobDiagnosticsConfig | null) {
  const main = mainStageLabel(j)
  const sub = substageLabel(j, materialMode)
  return [main, sub].filter(Boolean).join(' · ')
}

export function failedStageSummary(j: Job, materialMode?: string | JobDiagnosticsConfig | null) {
  const payload: any = parseJobPayload(j)
  const kind = String(j.kind || '').trim().toLowerCase()
  const failedStageRaw = kind === 'render'
    ? 'render'
    : String(payload.last_failed_stage || j.current_stage || payload.current_stage || '').trim().toLowerCase()
  if (!failedStageRaw) return ''
  const main = labelAutopilotStage(failedStageRaw, '') || mainStageLabel(j)
  const sub = failedStageRaw === 'render'
    ? labelRenderSubstage(String(j.render_substage || payload.render_substage || '').trim().toLowerCase(), '')
    : substageLabel({ ...j, current_stage: failedStageRaw } as Job, materialMode)
  return [main, sub].filter(Boolean).join(' · ')
}

export function autopilotFlowSteps(j: Job, materialMode?: string | JobDiagnosticsConfig | null): FlowStageView[] {
  const currentStage = normalizedStage(j)
  const currentSubstage = currentStage === 'render' ? normalizedRenderSubstage(j) : (normalizedSubstage(j) || messageSubstage(j, materialMode))
  const failed = String(j.status || '').trim().toLowerCase() === 'failed'
  const config = resolveConfig(materialMode)
  const stageOrder: Array<FlowStageView['key']> = ['storyboard', 'tts', 'media', 'render']
  const stageIndex = currentStage ? stageOrder.indexOf(currentStage as FlowStageView['key']) : -1
  const defs: Record<FlowStageView['key'], { label: string, substeps: Array<{ key: string, label: string }> }> = {
    storyboard: {
      label: '脚本分镜',
      substeps: [
        { key: 'generate_storyboard', label: '生成脚本与分镜' },
        { key: 'save_storyboard', label: '保存分镜' },
        { key: 'compliance', label: '合规检查' },
      ],
    },
    tts: {
      label: '配音字幕',
      substeps: [
        { key: 'generate_voice', label: '生成配音' },
        { key: 'generate_subtitles', label: '生成字幕' },
        { key: 'repair_subtitles', label: '修复字幕' },
      ],
    },
    media: {
      label: '画面准备',
      substeps: config?.mediaSubsteps || [],
    },
    render: {
      label: '最终成片',
      substeps: [
        { key: 'tts_prepare', label: '准备配音字幕' },
        { key: 'silent_track_prepare', label: '生成静音视频轨' },
        { key: 'mux_prepare', label: '混音与烧录字幕' },
        { key: 'finalize_output', label: '写入最终成片' },
      ],
    },
  }
  return stageOrder.map((key, index) => {
    const base = defs[key]
    const stageStatus: FlowStageView['status'] = failed && currentStage === key
      ? 'failed'
      : stageIndex < 0
        ? 'pending'
        : index < stageIndex
          ? 'completed'
          : index === stageIndex
            ? 'current'
            : 'pending'
    const activeSubIndex = base.substeps.findIndex((step) => step.key === currentSubstage)
    return {
      key,
      label: base.label,
      status: stageStatus,
      substeps: base.substeps.map((step, subIndex) => ({
        key: step.key,
        label: step.label,
        status: stageStatus === 'failed' && activeSubIndex === subIndex
          ? 'failed'
          : stageStatus !== 'current'
            ? (stageStatus === 'completed' ? 'completed' : 'pending')
            : activeSubIndex < 0
              ? (subIndex === 0 ? 'current' : 'pending')
              : subIndex < activeSubIndex
                ? 'completed'
                : subIndex === activeSubIndex
                  ? 'current'
                  : 'pending',
      })),
    }
  })
}

export function stageResumeLabel(j: Job) {
  const p: any = parseJobPayload(j)
  const stage = labelAutopilotStage(p.resume_from_stage || p.last_failed_stage, '')
  const sub = labelRenderSubstage(p.render_substage, '')
  return [stage, sub].filter(Boolean).join(' / ')
}

export function stageLabel(j: Job) {
  return labelJobFlowStage(j.kind)
}

export function jobMessageLabel(j: Job, materialMode?: string | JobDiagnosticsConfig | null) {
  const raw = String(j.message || '').trim()
  if (!raw) return ''
  const status = String(j.status || '').trim().toLowerCase()
  const main = mainStageLabel(j)
  const sub = substageLabel(j, materialMode)

  if (status === 'queued') {
    return main ? `${main}已加入队列，请稍候。` : '任务已加入队列，请稍候。'
  }

  if (status === 'paused') {
    return main ? `${main}已暂停。` : '任务已暂停。'
  }

  if (status === 'cancelled') {
    return main ? `${main}已取消。` : '任务已取消。'
  }

  if (status === 'done') {
    if (sub === '渲染完成') return '任务已完成。'
    if (main && sub) return `${main}已完成，当前结果：${sub}。`
    if (main) return `${main}已完成。`
    return raw
  }

  if (status === 'running') {
    if (main && sub) return `正在执行${main}，当前进度：${sub}。`
    if (main) return `正在执行${main}。`
  }

  return raw
}

export function humanHint(j: Job, materialMode?: string | JobDiagnosticsConfig | null) {
  const config = resolveConfig(materialMode)
  const p: any = parseJobPayload(j)
  const m = String(j.message || '')
  const sub = labelRenderSubstage(p.render_substage, '')
  if (sub && String(j.kind || '').trim().toLowerCase() === 'autopilot' && String(p.current_stage || '').trim().toLowerCase() === 'render') {
    if (sub.includes('静音视频轨')) return `当前正在渲染子阶段：${sub}。如果此前素材和配音没变，后续继续会优先复用已有结果。`
    if (sub.includes('配音字幕')) return `当前正在渲染子阶段：${sub}。如果脚本和语速没变，后续继续会优先复用已生成配音/字幕。`
    if (sub.includes('写入最终成片') || sub.includes('混音')) return `当前正在渲染子阶段：${sub}。如果前序成功，后续继续通常不会回到素材阶段。`
  }
  if (j.status === 'done' && (m.includes('已降级') || m.includes('复用') || m.includes('占位'))) return `系统已自动兜底：${m}`
  if (j.status !== 'failed') return ''
  const failedSummary = failedStageSummary(j)
  if (failedSummary) {
    if (recommendedAction(j) === 'continue_from_project') return `失败发生在：${failedSummary}。回到项目页后，系统会从这一段附近继续处理。`
    if (needsTts(j)) return `失败发生在：${failedSummary}。去“设置 -> 配音”检查当前配音方式和网络后重试。`
    if (needsMedia(j)) return `失败发生在：${failedSummary}。${config?.mediaFailureHint || '建议先修复当前画面准备配置后重试。'}`
    if (needsLlm(j)) return `失败发生在：${failedSummary}。建议先检查大模型配置后重试。`
  }
  if (recommendedAction(j) === 'go_settings_llm') return '大模型配置不可用：去“设置 -> 大模型”检查默认服务、服务地址、接口密钥和模型名称后重试。'
  if (recommendedAction(j) === 'go_settings_media') return '素材来源不可用：去“设置 -> 素材来源”检查素材服务配置，或先手动导入素材。'
  if (recommendedAction(j) === 'go_settings_tts') return '配音或字幕阶段失败：去“设置 -> 配音”检查当前配音方式和网络后重试。'
  if (recommendedAction(j) === 'continue_from_project') return '这个任务可回到项目页继续处理，系统会从失败阶段继续。'
  if (needsLlm(j)) return '大模型配置不可用：去“设置 -> 大模型”检查默认服务、服务地址、接口密钥和模型名称后重试。'
  if (needsMedia(j)) return config?.mode === 'ai' ? '生图配置不可用：去“设置 -> 生图模型”检查默认服务、服务地址、接口密钥和模型名称后重试。' : '素材来源不可用：去“设置 -> 素材来源”检查素材服务配置，或先手动导入素材。'
  if (needsTts(j)) return '配音或字幕阶段失败：去“设置 -> 配音”检查当前配音方式和网络后重试。'
  if (m.includes('最终成片') || m.includes('渲染')) return '渲染没有产出最终成片：回到项目页继续生成视频时，系统会优先复用已完成的素材、配音和静音视频轨。'
  return '执行失败了：可先打开项目页查看当前状态和修复建议，再按建议处理后重试。'
}
