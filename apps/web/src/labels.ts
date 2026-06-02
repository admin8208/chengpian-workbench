export function labelStatus(status: string | null | undefined) {
  const s = String(status || '').trim().toLowerCase()
  if (s === 'draft') return '未开始'
  if (s === 'processing') return '处理中'
  if (s === 'ready') return '可预览'
  if (s === 'failed') return '失败'
  if (s === 'queued') return '排队中'
  if (s === 'running') return '运行中'
  if (s === 'paused') return '已暂停'
  if (s === 'done') return '已完成'
  if (s === 'cancelled') return '已取消'
  return s || '未知状态'
}

export function labelAutopilotStage(stage: string | null | undefined, fallback = '当前阶段') {
  const s = String(stage || '').trim().toLowerCase()
  if (s === 'storyboard') return '脚本分镜'
  if (s === 'tts') return '配音字幕'
  if (s === 'media') return '画面准备'
  if (s === 'render') return '最终成片'
  return fallback
}

export function labelStage(stage: string | null | undefined, fallback = '处理中') {
  const s = String(stage || '').trim().toLowerCase()
  if (!s) return fallback
  return labelAutopilotStage(s, fallback)
}

export function labelRenderSubstage(stage: string | null | undefined, fallback = '') {
  const s = String(stage || '').trim().toLowerCase()
  if (s === 'tts_prepare') return '准备配音字幕'
  if (s === 'tts_ready') return '已复用/生成配音字幕'
  if (s === 'silent_track_prepare') return '生成静音视频轨'
  if (s === 'silent_track_ready') return '已复用/生成静音视频轨'
  if (s === 'mux_prepare') return '混音与烧录字幕'
  if (s === 'finalize_output') return '写入最终成片'
  if (s === 'done') return '渲染完成'
  return fallback
}

export function labelJobSubstage(stage: string | null | undefined, fallback = '执行中') {
  const s = String(stage || '').trim().toLowerCase()
  if (!s) return fallback
  if (s === 'compliance') return '合规检查'
  if (s === 'save_storyboard') return '保存分镜'
  if (s === 'generate_storyboard') return '生成脚本与分镜'
  if (s === 'storyboard_running') return '脚本分镜处理中'
  if (s === 'generate_images') return '生成镜头图'
  if (s === 'verify_images') return '检查缺失镜头图'
  if (s === 'media_round_1') return '自动匹配素材'
  if (s === 'media_round_2') return '补素材第 2 轮'
  if (s === 'media_round_3') return '补素材第 3 轮'
  if (s === 'media_repair') return '质量修复补素材'
  if (s === 'media_verify') return '缺失校验'
  if (s === 'media_running') return '画面准备处理中'
  if (s === 'repair_subtitles') return '修复字幕'
  if (s === 'silent_voice_fallback') return '生成静音兜底音轨'
  if (s === 'generate_subtitles') return '生成字幕'
  if (s === 'generate_voice') return '生成配音'
  if (s === 'reuse_tts') return '复用配音字幕'
  if (s === 'tts_running') return '配音字幕处理中'
  return fallback
}

export function labelJobKind(kind: string | null | undefined) {
  const k = String(kind || '').trim().toLowerCase()
  if (k === 'autopilot') return '自动生成视频'
  if (k === 'autofill_media') return '自动填充素材'
  if (k === 'images') return '批量生成镜头图片'
  if (k === 'scene_image') return '生成镜头图片'
  if (k === 'render') return '最终成片'
  if (k === 'ab_hooks') return '多版本变体'
  if (k === 'tts_offline_install') return '安装离线配音'
  if (k === 'tts_offline_install_all_compatible') return '安装全部兼容音色'
  if (k === 'script_prepare') return '文案生成'
  if (k === 'scheduled_cleanup_task') return '系统清理'
  return k || '系统任务'
}

export function labelBlockingComponent(component: string | null | undefined, fallback = '未知阻塞点') {
  const c = String(component || '').trim().toLowerCase()
  if (c === 'llm') return '大模型'
  if (c === 'media') return '素材来源'
  if (c === 'tts') return '配音'
  if (c === 'image') return '图片生成'
  if (c === 'render') return '渲染'
  if (c === 'project') return '项目内容'
  return c ? fallback : ''
}

export function labelRecommendedAction(action: string | null | undefined, fallback = '处理建议') {
  const a = String(action || '').trim().toLowerCase()
  if (a === 'go_settings_llm') return '前往设置检查大模型'
  if (a === 'go_settings_media') return '前往设置检查素材来源'
  if (a === 'go_settings_tts') return '前往设置检查配音'
  if (a === 'go_settings_image') return '前往设置检查图片生成'
  if (a === 'continue_from_project') return '回到项目页继续处理'
  if (a === 'open_project') return '打开项目检查并处理'
  if (a === 'render') return '重新进入渲染阶段处理'
  return a ? fallback : ''
}

export function labelErrorCode(code: string | null | undefined, fallback = '未知错误') {
  const c = String(code || '').trim().toLowerCase()
  if (c === 'source_text_missing') return '原文或要点为空'
  if (c === 'llm_config_missing') return '大模型配置缺失'
  if (c === 'storyboard_failed') return '脚本分镜生成失败'
  if (c === 'image_config_missing') return '图片生成配置缺失'
  if (c === 'media_provider_unavailable') return '素材来源不可用'
  if (c === 'tts_unavailable') return '配音服务不可用'
  if (c === 'tts_audio_env_unavailable') return '配音音频环境不可用'
  if (c === 'project_missing') return '项目不存在'
  if (c === 'render_failed') return '渲染失败'
  if (c === 'final_missing') return '最终成片文件缺失'
  if (c === 'channel_pack_missing') return '频道内容包不存在'
  if (c === 'preflight_failed') return '前置检查失败'
  return c ? fallback : ''
}

export function labelJobFlowStage(kind: string | null | undefined) {
  const k = String(kind || '').trim().toLowerCase()
  if (k === 'autofill_media' || k === 'images' || k === 'scene_image') return '4 画面准备'
  if (k === 'tts_offline_install') return '3 配音字幕'
  if (k === 'render' || k === 'autopilot') return '5 最终成片'
  return '系统任务'
}
