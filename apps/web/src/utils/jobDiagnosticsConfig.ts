export type JobDiagnosticsMode = 'ai' | 'network'

export type JobDiagnosticsConfig = {
  mode: JobDiagnosticsMode
  mediaRunningLabel: string
  mediaSubsteps: Array<{ key: string; label: string }>
  inferMediaSubstage: (message: string) => string
  mediaFailureHint: string
}

export const aiJobDiagnosticsConfig: JobDiagnosticsConfig = {
  mode: 'ai',
  mediaRunningLabel: '画面准备处理中',
  mediaSubsteps: [
    { key: 'generate_images', label: '生成镜头图' },
    { key: 'verify_images', label: '检查缺失镜头图' },
  ],
  inferMediaSubstage: (message: string) => {
    if (message.includes('镜头图') || message.includes('生图') || message.includes('图片')) return 'generate_images'
    if (message.includes('缺失') || message.includes('补齐') || message.includes('校验')) return 'verify_images'
    return 'media_running'
  },
  mediaFailureHint: '建议先修复生图配置或补齐镜头图后重试。',
}

export const networkJobDiagnosticsConfig: JobDiagnosticsConfig = {
  mode: 'network',
  mediaRunningLabel: '画面准备处理中',
  mediaSubsteps: [
    { key: 'media_round_1', label: '自动匹配素材' },
    { key: 'media_round_2', label: '补素材第 2 轮' },
    { key: 'media_round_3', label: '补素材第 3 轮' },
    { key: 'media_repair', label: '质量修复补素材' },
    { key: 'media_verify', label: '缺失校验' },
  ],
  inferMediaSubstage: (message: string) => {
    if (message.includes('第 3 轮')) return 'media_round_3'
    if (message.includes('第 2 轮')) return 'media_round_2'
    if (message.includes('修复') || message.includes('质量')) return 'media_repair'
    if (message.includes('缺失') || message.includes('校验')) return 'media_verify'
    if (message.includes('匹配') || message.includes('补素材') || message.includes('素材')) return 'media_round_1'
    return 'media_running'
  },
  mediaFailureHint: '建议先修复素材来源或补齐画面资源后重试。',
}
