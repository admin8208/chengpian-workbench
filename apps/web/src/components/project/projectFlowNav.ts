import { computed, type ComputedRef } from 'vue'
import { Document, Film, Mic, PictureFilled, VideoPlay } from '@element-plus/icons-vue'

export type FlowStep = 'input' | 'storyboard' | 'voice' | 'media' | 'render'

export interface StepInfo {
  key: FlowStep
  label: string
  desc: string
  icon: any
  color: string
  tips: string
}

export interface FlowNavProps {
  currentStep: FlowStep
  recommendedStep: FlowStep
  jobStatus: 'idle' | 'queued' | 'running' | 'paused' | 'failed' | 'done' | ''
  jobProgress: number
  jobMessage: string
  sceneCount: number
  missingAssetCount: number
  finalExists: boolean
  canProceed: boolean
  inputMode?: 'text' | 'audio'
  materialMode?: 'ai' | 'network'
  uiLabels?: {
    modeName?: string
    storyboardStepLabel?: string
    storyboardStepDesc?: string
    storyboardStepTips?: string
    storyboardIssueLabel?: string
    storyboardReadyLabel?: string
  }
  hasConfirmedBaseline?: boolean
  hasDraftScript?: boolean
}

const baseSteps: StepInfo[] = [
  {
    key: 'input',
    label: '输入确认',
    desc: '主题、原文、主音频、脚本基线',
    icon: Document,
    color: '#3b82f6',
    tips: '先确定内容从哪里来，再在同一页生成、修改并确认脚本或转写结果。',
  },
  {
    key: 'storyboard',
    label: '脚本分镜',
    desc: '镜头结构与旁白拆分',
    icon: Film,
    color: '#10b981',
    tips: '系统会根据已确认的文案或转写结果生成镜头结构、旁白分段和画面提示。',
  },
  {
    key: 'voice',
    label: '配音与字幕',
    desc: '声音与字幕收口',
    icon: Mic,
    color: '#f59e0b',
    tips: '文案驱动会生成配音；音频驱动会直接复用上传音频。两种模式都会在这里整理字幕。',
  },
  {
    key: 'media',
    label: '画面准备',
    desc: 'AI 生图或网络素材匹配',
    icon: PictureFilled,
    color: '#14b8a6',
    tips: '系统会按当前画面模式生成镜头图，或自动搜索、导入并绑定网络素材。',
  },
  {
    key: 'render',
    label: '最终成片',
    desc: '查看正式版与历史版',
    icon: VideoPlay,
    color: '#8b5cf6',
    tips: '系统会直接生成一个最终版本，完成后在这里查看',
  },
]

export function useProjectFlowNav(props: FlowNavProps): {
  resolvedSteps: ComputedRef<StepInfo[]>
  nextStep: ComputedRef<FlowStep | null>
  nextStepInfo: ComputedRef<StepInfo | null>
  stepIndex: (step: FlowStep) => number
  isStepActive: (step: FlowStep) => boolean
  isStepCompleted: (step: FlowStep) => boolean
  isStepCurrent: (step: FlowStep) => boolean
  getStepStatus: (step: FlowStep) => 'pending' | 'active' | 'running' | 'completed' | 'error'
  getStepSummary: (step: FlowStep) => string
} {
  const resolvedSteps = computed(() => baseSteps.map((step) => {
    if (step.key === 'voice') {
      return {
        ...step,
        label: props.inputMode === 'audio' ? '音轨与字幕' : '配音与字幕',
        desc: props.inputMode === 'audio' ? '主音频与字幕收口' : '配音与字幕收口',
      }
    }
    if (step.key === 'input') {
      return {
        ...step,
        label: props.inputMode === 'audio' ? '转写确认' : '文案确认',
        desc: props.inputMode === 'audio' ? '主音频上传、转写与脚本基线' : '主题、原文与脚本基线',
      }
    }
    if (step.key === 'media') {
      return {
        ...step,
        label: props.uiLabels?.storyboardStepLabel || (props.materialMode === 'ai' ? '智能出图' : '素材匹配'),
        desc: props.uiLabels?.storyboardStepDesc || (props.materialMode === 'ai' ? '镜头图生成与缺失校验' : '素材检索、导入与绑定'),
        tips: props.uiLabels?.storyboardStepTips || step.tips,
      }
    }
    if (step.key === 'render') {
      return {
        ...step,
        desc: '查看正式版与历史版',
      }
    }
    return step
  }))

  function stepIndex(step: FlowStep): number {
    return resolvedSteps.value.findIndex((item) => item.key === step)
  }

  function isStepActive(step: FlowStep): boolean {
    return props.currentStep === step
  }

  function isStepCompleted(step: FlowStep): boolean {
    const idx = stepIndex(step)
    const currentIdx = stepIndex(props.recommendedStep)
    return idx < currentIdx
  }

  function isStepCurrent(step: FlowStep): boolean {
    return props.recommendedStep === step
  }

  function getStepStatus(step: FlowStep): 'pending' | 'active' | 'running' | 'completed' | 'error' {
    if (isStepCompleted(step)) return 'completed'
    if (isStepActive(step)) {
      if (props.jobStatus === 'running') return 'running'
      if (props.jobStatus === 'failed') return 'error'
      return 'active'
    }
    return 'pending'
  }

  function getStepSummary(step: FlowStep): string {
    if (step === 'input') {
      if (Boolean(props.hasConfirmedBaseline)) return props.inputMode === 'audio' ? '转写已确认' : '文案已确认'
      if (Boolean(props.hasDraftScript)) return props.inputMode === 'audio' ? '待确认转写' : '待确认文案'
      return props.inputMode === 'audio' ? '确定音频与转写基线' : '确定主题并生成文案'
    }
    if (step === 'storyboard') {
      if (!Boolean(props.hasConfirmedBaseline)) return '先确认文案基线'
      if (props.sceneCount === 0) return '等待生成脚本分镜'
      return `${props.sceneCount} 个镜头分镜已生成`
    }
    if (step === 'media') {
      if (!Boolean(props.hasConfirmedBaseline)) return '先确认文案基线'
      if (props.sceneCount === 0) return '等待脚本分镜'
      const issues = props.missingAssetCount
      if (issues > 0) return `${props.sceneCount} 镜头 · ${issues} 个${props.uiLabels?.storyboardIssueLabel || '画面'}问题`
      return `${props.sceneCount} 镜头${props.uiLabels?.storyboardReadyLabel || '已就绪'}`
    }
    if (step === 'voice') {
      return '音轨与字幕整理'
    }
    if (step === 'render') {
      if (props.finalExists) return '已有最终成片'
      return '等待生成最终成片'
    }
    return ''
  }

  function getNextStep(current: FlowStep): FlowStep | null {
    const currentIdx = stepIndex(current)
    if (currentIdx < baseSteps.length - 1) {
      return resolvedSteps.value[currentIdx + 1]?.key || null
    }
    return null
  }

  const nextStep = computed(() => getNextStep(props.currentStep))
  const nextStepInfo = computed(() => {
    if (!nextStep.value) return null
    return resolvedSteps.value.find((step) => step.key === nextStep.value) || null
  })

  return {
    resolvedSteps,
    nextStep,
    nextStepInfo,
    stepIndex,
    isStepActive,
    isStepCompleted,
    isStepCurrent,
    getStepStatus,
    getStepSummary,
  }
}
