export type ChannelPack = {
  key: string
  name: string
  description: string
}

export type Project = {
  id: number
  title: string
  workflow: 'mix' | string
  channel_key: string
  status: string
  script: string
  script_source?: string
  source_text?: string
  character_profile?: string
  publish_title?: string
  publish_hashtags?: string
  render_config?: Record<string, any>
  voice_asset_id?: number | null
  subtitle_asset_id?: number | null
  confirmed_baseline_revision_id?: number | null
  current_pipeline_run_id?: number | null
  role_image_url?: string | null
  voice_url?: string | null
  subtitle_url?: string | null
  created_at: string
  updated_at: string
}

export type Scene = {
  id: number
  project_id: number
  idx: number
  narration: string
  media_query?: string
  image_prompt: string
  image_negative?: string
  duration_sec: number
  image_asset_id: number | null
  image_url?: string | null
  meta?: any
  status: string
}

export type SceneBindAssetIn = {
  asset_id: number
}

export type ProjectDetail = Project & {
  scenes: Scene[]
}

export type AuthStatus = {
  enabled: boolean
  authenticated: boolean
  setup_required: boolean
  username?: string | null
  role?: string
  is_admin?: boolean
}

export type UserAccount = {
  id: number
  username: string
  enabled: boolean
  created_at: string
  updated_at: string
}

export type ProjectSummary = {
  project_id: number
  project_title: string
  workflow: string
  material_mode?: 'ai' | 'network' | string
  status: string
  confirmed_baseline_revision_id?: number | null
  current_pipeline_run_id?: number | null
  scene_count: number
  missing_asset_count: number
  review_count: number
  duplicate_asset_count: number
  final_exists: boolean
  final_size: number
  history_count: number
  export_count: number
  tts_backend: string
  tts_backend_label: string
  subtitle_style: string
  subtitle_style_label: string
  last_job_kind?: string | null
  last_job_status?: string | null
  last_job_message?: string | null
  last_job_stage?: string | null
  continue_stage?: string | null
  suggestions: string[]
  fix_actions?: string[]
  content_reasonableness_score?: number
  content_reasonableness_items?: string[]
  content_reasonableness_metrics?: Record<string, number>
  input_mode?: 'text' | 'audio' | string
}

export type ProjectRuntime = {
  project_id: number
  project_title: string
  workflow: string
  material_mode?: 'ai' | 'network' | string
  project_status: string
  confirmed_baseline_revision_id?: number | null
  current_pipeline_run_id?: number | null
  workflow_stage?: string | null
  continue_stage?: string | null
  active_job_status?: string | null
  next_action: string
  last_job_kind?: string | null
  last_job_status?: string | null
  last_job_message?: string | null
  final_exists: boolean
  missing_asset_count: number
  review_count: number
  duplicate_asset_count: number
  blocker_items: string[]
  suggested_fix_actions: string[]
  summary_suggestions: string[]
  current_job?: Job | null
  summary_job?: Job | null
}

export type ProjectQuality = {
  score: number
  issues: string[]
  strengths: string[]
  suggestions: string[]
  metrics?: Record<string, number>
  platform_notes?: Record<string, string[]>
}

export type TtsPreview = {
  ok: boolean
  url?: string | null
  error?: string | null
}

export type OfflineVoiceInfo = {
  voice_id: string
  label: string
  quality?: string
  sample_rate?: number
  installed?: boolean
  compatible?: boolean
  reason?: string
  phoneme_type?: string
  piper_version?: string
}

export type EdgeVoiceInfo = {
  voice_id: string
  label: string
  locale?: string
  gender?: string
}

export type TtsStatus = {
  backend: 'auto' | 'edge' | 'offline_piper' | string
  offline_voice_id: string
  edge_voice_id: string
  default_voice_rate: string
  edge_synthesis_ok: boolean
  edge_checked?: boolean
  edge_detail?: string
  offline_installed: boolean
  offline_ok: boolean
  offline_detail?: string
  offline_installed_voice_ids?: string[]
  offline_installed_voice_count?: number
  available_offline_voice_ids?: string[]
  available_offline_voice_count?: number
  available_offline_voices?: OfflineVoiceInfo[]
  available_edge_voice_ids?: string[]
  available_edge_voice_count?: number
  available_edge_zh_cn_voice_count?: number
  available_edge_voices?: EdgeVoiceInfo[]
}

export type Job = {
  id: number
  kind: string
  project_id: number
  parent_job_id?: number | null
  root_job_id?: number | null
  retry_seq?: number
  project_title?: string | null
  project_workflow?: string | null
  status: string
  progress: number
  message: string
  payload_json?: string
  cancel_requested?: boolean
  pause_requested?: boolean
  cancel_source?: string
  cancel_reason?: string
  worker_id?: string
  worker_pid?: number
  worker_started_at?: string | null
  worker_heartbeat_at?: string | null
  current_stage?: string | null
  current_substage?: string | null
  render_substage?: string | null
  error_code?: string | null
  blocking_component?: string | null
  recommended_action?: string | null
  recoverable?: boolean | null
  created_at: string
  updated_at: string
}

export type FeedTag = {
  label: string
  type: 'info' | 'warning' | 'danger' | 'success'
}

export type ProjectFeedJob = {
  id: number
  kind: string
  kind_label: string
  status: string
  status_label: string
  progress: number
  stage_label: string
  substage_label: string
  stage_summary: string
  message_label: string
  hint: string
  updated_at: string
  updated_at_text: string
  resume_label: string
  chain_attempts_label: string
}

export type ProjectCenterItem = {
  project_id: number
  title: string
  workflow: string
  channel_key: string
  material_mode: 'ai' | 'network' | string
  material_mode_label: string
  open_path: string
  tone: '' | 'success' | 'warning' | 'danger'
  status: string
  status_label: string
  stage_text: string
  notice: string
  action_key: 'open_project' | 'continue_project' | 'rerun_project'
  action_label: string
  tags: FeedTag[]
  final_exists: boolean
  emphasize_asset_issues: boolean
  missing_asset_label: string
  missing_asset_count: number
  duplicate_asset_count: number
  continue_stage_label: string
  needs_llm_settings: boolean
  needs_media_settings: boolean
  needs_tts_settings: boolean
  can_delete: boolean
  updated_at: string
  updated_at_text: string
  current_job?: ProjectFeedJob | null
  current_job_is_active: boolean
}

export type ProjectCenterStats = {
  all: number
  running: number
  failed: number
  final_ready: number
}

export type ProjectCenterFeed = {
  stats: ProjectCenterStats
  items: ProjectCenterItem[]
  server_time: string
  next_cursor: string
  rebuilding?: boolean
}

export type JobCenterHistoryItem = {
  job_id: number
  execution_label: string
  status: string
  status_label: string
  status_tone: 'info' | 'warning' | 'danger' | 'success'
  stage_label: string
  substage_label: string
  updated_at: string
  updated_at_text: string
}

export type JobCenterItem = {
  entry_key: string
  entry_type: 'chain' | 'job'
  project_id: number
  project_title: string
  project_material_mode: 'ai' | 'network' | string
  project_open_path: string
  project_final_exists: boolean
  status: string
  status_label: string
  status_tone: 'info' | 'warning' | 'danger' | 'success'
  job_id: number
  root_job_id?: number | null
  attempt_count: number
  chain_attempts_label: string
  job_kind: string
  job_kind_label: string
  stage_label: string
  substage_label: string
  message_label: string
  human_hint: string
  progress: number
  updated_at: string
  updated_at_text: string
  error_code?: string | null
  error_code_label: string
  blocking_component?: string | null
  blocking_component_label: string
  recommended_action?: string | null
  recommended_action_label: string
  is_active: boolean
  is_deletable: boolean
  history: JobCenterHistoryItem[]
}

export type JobCenterStats = {
  all: number
  active: number
  failed: number
  done: number
  cancelled: number
}

export type JobCenterFeed = {
  stats: JobCenterStats
  items: JobCenterItem[]
  server_time: string
  next_cursor: string
  rebuilding?: boolean
}

export type LlmProvider = {
  id: number
  name: string
  type: string
  base_url: string
  default_model: string
  enabled: boolean
  is_default: boolean
  api_key?: string
}

export type LlmStatus = {
  has_default: boolean
  default_provider_id?: number | null
  default_provider_name?: string | null
  default_provider_type?: string | null
  default_model?: string | null
  has_api_key?: boolean
}

export type ImageProvider = {
  id: number
  name: string
  type: 'openai_compat' | string
  base_url: string
  default_model: string
  enabled: boolean
  is_default: boolean
  api_key?: string
}

export type ImageStatus = {
  has_default: boolean
  default_provider_id?: number | null
  default_provider_name?: string | null
  default_provider_type?: string | null
  default_model?: string | null
  has_api_key?: boolean
}

export type HealthComponent = {
  ok: boolean
  status: string
  detail?: string | null
  hint?: string | null
}

export type Health = {
  ok: boolean
  components: Record<string, HealthComponent>
}

export type Asset = {
  id: number
  kind: 'image' | 'audio' | 'video' | 'other' | string
  tag?: string | null
  project_id?: number | null
  scene_id?: number | null
  url: string
  mime?: string | null
  meta?: Record<string, any>
  created_at: string
}

export type WebMediaItem = {
  provider: string
  kind: 'image' | 'video' | 'audio' | string
  title: string
  page_url: string
  file_url: string
  thumb_url?: string | null
  preview_url?: string | null
  mime?: string
  width?: number | null
  height?: number | null
  duration_sec?: number | null
  license_short?: string
  license_url?: string | null
  author?: string
  attribution?: string
}

export type MediaProvider = 'wikimedia' | 'pexels' | 'pixabay'

export type MediaProviderStatus = {
  provider: MediaProvider
  ok: boolean
  has_api_key: boolean
  api_key?: string
  detail?: string | null
  supported_kinds?: Array<'image' | 'video' | 'audio'>
}

export type WebSearchResult = {
  ok: boolean
  items: WebMediaItem[]
}

export const DEFAULT_CHANNEL_PACKS: ChannelPack[] = [
  { key: 'emotion', name: '情感关系', description: '关系冲突、边界感、失望积累等情绪话题。' },
  { key: 'career', name: '职场成长', description: '职场冲突、沟通、加班、绩效等现实场景。' },
  { key: 'family_cn', name: '中式家庭', description: '家庭关系、代际沟通、情感压力与边界。' },
  { key: 'history', name: '历史悬疑', description: '历史人物、线索、反转和悬念表达。' },
]

// Cloud storage types
export interface CloudConfig {
  url?: string
  username?: string
  password?: string
  access_token?: string
  refresh_token?: string
  client_id?: string
  client_secret?: string
  path?: string
}

export interface CloudFileItem {
  name: string
  path: string
  is_dir: boolean
  size: number
  type: string
  modified: string
  file_id?: string
  id?: string
  fs_id?: number | string
}

export interface CloudTestResult {
  success: boolean
  message: string
}

export interface CloudListResult {
  files: CloudFileItem[]
  current_path: string
}

export interface CloudImportResult {
  success: boolean
  message: string
  asset_id?: number
}
