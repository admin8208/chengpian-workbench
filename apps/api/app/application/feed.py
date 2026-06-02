import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import desc
from sqlmodel import select

from app.access_control import current_principal, visible_project_ids, visible_project_query
from app.api_common import get_project_workflow_meta, latest_autopilot_job, resolve_final_export_status
from app.application.projects.service import project_summary_and_quality
from app.db import session_scope
from app.material_policies import project_material_mode
from app.models import Job, Project
from app.modules.pipeline.repository import get_pipeline_run
from app.schemas import (
    FeedTagOut,
    JobCenterFeedOut,
    JobCenterHistoryItemOut,
    JobCenterItemOut,
    JobCenterStatsOut,
    ProjectCenterFeedOut,
    ProjectCenterItemOut,
    ProjectCenterStatsOut,
    ProjectFeedJobOut,
)
from app.projection_store import (
    delete_job_projections,
    delete_project_projection,
    load_job_projection_rows,
    load_project_projection_rows,
    replace_job_projections,
    upsert_project_projection,
)
from app.services.autopilot_state import autopilot_continue_stage
from app.services.job_presenters import _job_stage_fields, job_error_meta
from app.time_utils import now_utc


ACTIVE_JOB_STATUSES = {"queued", "running", "paused"}
PROJECT_JOB_KINDS = {"autopilot", "autofill_media", "images", "scene_image", "render", "script_prepare"}


@dataclass
class JobChain:
    root_id: int
    nodes: list[Job]
    head: Job


def _format_time(dt: datetime | None) -> str:
    if not dt:
        return "-"
    try:
        return dt.astimezone().strftime("%Y-%m-%d %H:%M")
    except Exception:
        return str(dt)


def _normalize(value: str | None) -> str:
    return str(value or "").strip().lower()


def _label_status(status: str | None) -> str:
    s = _normalize(status)
    if s == "draft":
        return "未开始"
    if s == "processing":
        return "处理中"
    if s == "ready":
        return "可预览"
    if s == "failed":
        return "失败"
    if s == "queued":
        return "排队中"
    if s == "running":
        return "运行中"
    if s == "paused":
        return "已暂停"
    if s == "done":
        return "已完成"
    if s == "cancelled":
        return "已取消"
    return s or "未知状态"


def _label_autopilot_stage(stage: str | None, fallback: str = "当前阶段") -> str:
    s = _normalize(stage)
    if s == "storyboard":
        return "脚本分镜"
    if s == "tts":
        return "配音字幕"
    if s == "media":
        return "画面准备"
    if s == "render":
        return "最终成片"
    return fallback


def _label_render_substage(stage: str | None, fallback: str = "") -> str:
    s = _normalize(stage)
    if s == "tts_prepare":
        return "准备配音字幕"
    if s == "tts_ready":
        return "已复用/生成配音字幕"
    if s == "silent_track_prepare":
        return "生成静音视频轨"
    if s == "silent_track_ready":
        return "已复用/生成静音视频轨"
    if s == "mux_prepare":
        return "混音与烧录字幕"
    if s == "finalize_output":
        return "写入最终成片"
    if s == "done":
        return "渲染完成"
    return fallback


def _label_job_substage(stage: str | None, fallback: str = "执行中") -> str:
    s = _normalize(stage)
    if not s:
        return fallback
    mapping = {
        "compliance": "合规检查",
        "save_storyboard": "保存分镜",
        "generate_storyboard": "生成脚本与分镜",
        "storyboard_running": "脚本分镜处理中",
        "generate_images": "生成镜头图",
        "verify_images": "检查缺失镜头图",
        "media_round_1": "自动匹配素材",
        "media_round_2": "补素材第 2 轮",
        "media_round_3": "补素材第 3 轮",
        "media_repair": "质量修复补素材",
        "media_verify": "缺失校验",
        "media_running": "画面准备处理中",
        "repair_subtitles": "修复字幕",
        "silent_voice_fallback": "生成静音兜底音轨",
        "generate_subtitles": "生成字幕",
        "generate_voice": "生成配音",
        "reuse_tts": "复用配音字幕",
        "tts_running": "配音字幕处理中",
    }
    return mapping.get(s, fallback)


def _label_job_kind(kind: str | None) -> str:
    k = _normalize(kind)
    mapping = {
        "autopilot": "自动生成视频",
        "autofill_media": "自动填充素材",
        "images": "批量生成镜头图片",
        "scene_image": "生成镜头图片",
        "render": "最终成片",
        "ab_hooks": "多版本变体",
        "tts_offline_install": "安装离线配音",
        "tts_offline_install_all_compatible": "安装全部兼容音色",
        "script_prepare": "文案生成",
        "scheduled_cleanup_task": "系统清理",
    }
    return mapping.get(k, k or "系统任务")


def _label_blocking_component(component: str | None) -> str:
    c = _normalize(component)
    mapping = {
        "llm": "大模型",
        "media": "素材来源",
        "tts": "配音",
        "image": "图片生成",
        "render": "渲染",
        "project": "项目内容",
    }
    return mapping.get(c, "未知阻塞点" if c else "")


def _label_recommended_action(action: str | None) -> str:
    a = _normalize(action)
    mapping = {
        "go_settings_llm": "前往设置检查大模型",
        "go_settings_media": "前往设置检查素材来源",
        "go_settings_tts": "前往设置检查配音",
        "go_settings_image": "前往设置检查图片生成",
        "continue_from_project": "回到项目页继续处理",
        "open_project": "打开项目检查并处理",
        "render": "重新进入渲染阶段处理",
    }
    return mapping.get(a, "处理建议" if a else "")


def _label_error_code(code: str | None) -> str:
    c = _normalize(code)
    mapping = {
        "source_text_missing": "原文或要点为空",
        "llm_config_missing": "大模型配置缺失",
        "storyboard_failed": "脚本分镜生成失败",
        "image_config_missing": "图片生成配置缺失",
        "media_provider_unavailable": "素材来源不可用",
        "tts_unavailable": "配音服务不可用",
        "tts_audio_env_unavailable": "配音音频环境不可用",
        "project_missing": "项目不存在",
        "render_failed": "渲染失败",
        "final_missing": "最终成片文件缺失",
        "channel_pack_missing": "频道内容包不存在",
        "preflight_failed": "前置检查失败",
    }
    return mapping.get(c, "未知错误" if c else "")


def _parse_payload(job: Job) -> dict:
    try:
        obj = json.loads(str(getattr(job, "payload_json", "{}") or "{}"))
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _job_root_id(job: Job) -> int:
    rid = int(getattr(job, "root_job_id", 0) or 0)
    return rid if rid > 0 else int(getattr(job, "id", 0) or 0)


def _build_job_chains(rows: list[Job]) -> list[JobChain]:
    groups: dict[int, list[Job]] = defaultdict(list)
    for job in rows:
        groups[_job_root_id(job)].append(job)
    chains: list[JobChain] = []
    for root_id, nodes in groups.items():
        ordered = sorted(nodes, key=lambda item: ((item.updated_at or now_utc()), int(item.id or 0)), reverse=True)
        active = next((node for node in ordered if _normalize(node.status) in ACTIVE_JOB_STATUSES), None)
        head = active or ordered[0]
        chains.append(JobChain(root_id=root_id, nodes=ordered, head=head))
    chains.sort(key=lambda chain: ((chain.head.updated_at or now_utc()), int(chain.head.id or 0)), reverse=True)
    return chains


def _chain_attempts_label(chain: JobChain | None) -> str:
    if not chain:
        return ""
    attempts = len(chain.nodes)
    if attempts <= 1:
        return ""
    return f"断点续传 {attempts - 1} 次（共 {attempts} 条记录）"


def _autopilot_execution_label(job: Job) -> str:
    payload = _parse_payload(job)
    retry_seq = max(0, int(getattr(job, "retry_seq", 0) or 0))
    resume_stage = _normalize(payload.get("resume_from_stage"))
    render_substage = _normalize(payload.get("render_substage"))
    message = str(getattr(job, "message", "") or "").strip()
    if message == "重新开始":
        return f"第 {retry_seq + 1} 次执行 · 重新开始" if retry_seq > 0 else "重新开始"
    if resume_stage:
        stage = _label_autopilot_stage(resume_stage, resume_stage)
        sub = _label_render_substage(render_substage, "") if resume_stage == "render" else ""
        suffix = " / ".join([part for part in (stage, sub) if part])
        return f"第 {retry_seq + 1} 次执行 · 从{suffix}继续" if retry_seq > 0 else f"从{suffix}继续"
    if retry_seq > 0:
        return f"第 {retry_seq + 1} 次执行"
    return "首次执行"


def _needs_llm(job: Job) -> bool:
    meta = job_error_meta(job)
    return _normalize(meta.get("blocking_component")) == "llm" or _normalize(meta.get("recommended_action")) == "go_settings_llm"


def _needs_media(job: Job) -> bool:
    meta = job_error_meta(job)
    return _normalize(meta.get("blocking_component")) == "media" or _normalize(meta.get("recommended_action")) == "go_settings_media"


def _needs_tts(job: Job) -> bool:
    meta = job_error_meta(job)
    return _normalize(meta.get("blocking_component")) == "tts" or _normalize(meta.get("recommended_action")) == "go_settings_tts"


def _message_substage(job: Job, stage: str) -> str:
    msg = str(getattr(job, "message", "") or "").strip()
    low = msg.lower()
    if stage == "storyboard":
        if "合规" in msg:
            return "compliance"
        if "保存" in msg:
            return "save_storyboard"
        if "脚本" in msg or "分镜" in msg:
            return "generate_storyboard"
        return "storyboard_running"
    if stage == "media":
        if "第 3 轮" in msg:
            return "media_round_3"
        if "第 2 轮" in msg:
            return "media_round_2"
        if "修复" in msg:
            return "media_repair"
        if "校验" in msg or "缺失" in msg:
            return "media_verify"
        return "media_round_1" if msg else "media_running"
    if stage == "tts":
        if "重建字幕" in msg or "自动重建字幕" in msg or "修复字幕" in msg:
            return "repair_subtitles"
        if "静音音轨" in msg:
            return "silent_voice_fallback"
        if "字幕" in msg:
            return "generate_subtitles"
        if "配音" in msg:
            return "generate_voice"
        if "reuse" in low or "复用" in msg:
            return "reuse_tts"
        return "tts_running"
    return ""


def _job_stage_triplet(session, job: Job, project: Project | None) -> tuple[str, str, str]:
    payload = _parse_payload(job)
    pipeline_run = get_pipeline_run(session, getattr(project, "current_pipeline_run_id", None)) if project else None
    current_stage, current_substage, render_substage = _job_stage_fields(job, payload, pipeline_run)
    stage = _normalize(current_stage)
    substage = _normalize(current_substage)
    render = _normalize(render_substage)
    return stage, substage, render


def _main_stage_label(session, job: Job, project: Project | None) -> str:
    kind = _normalize(job.kind)
    stage, _substage, _render = _job_stage_triplet(session, job, project)
    if stage:
        return _label_autopilot_stage(stage, _label_job_kind(kind))
    if kind in {"images", "scene_image", "autofill_media"}:
        return "画面准备"
    if kind == "render":
        return "最终成片"
    return _label_job_kind(kind)


def _substage_label(session, job: Job, project: Project | None) -> str:
    stage, substage, render = _job_stage_triplet(session, job, project)
    if stage == "render":
        return _label_render_substage(render, "渲染处理中" if render else "")
    resolved = substage or _message_substage(job, stage)
    if stage == "storyboard":
        return _label_job_substage(resolved, "脚本分镜处理中")
    if stage == "media":
        return _label_job_substage(resolved, "画面准备处理中")
    if stage == "tts":
        return _label_job_substage(resolved, "配音字幕处理中")
    return _label_job_substage(resolved, "")


def _stage_summary(session, job: Job, project: Project | None) -> str:
    parts = [_main_stage_label(session, job, project), _substage_label(session, job, project)]
    return " · ".join([part for part in parts if part])


def _failed_stage_summary(session, job: Job, project: Project | None) -> str:
    payload = _parse_payload(job)
    kind = _normalize(job.kind)
    failed_stage = "render" if kind == "render" else _normalize(payload.get("last_failed_stage") or getattr(job, "current_stage", "") or payload.get("current_stage"))
    if not failed_stage:
        return ""
    if failed_stage == "render":
        sub = _label_render_substage(_normalize(getattr(job, "render_substage", "") or payload.get("render_substage")), "")
        return " · ".join([part for part in (_label_autopilot_stage(failed_stage, ""), sub) if part])
    return _label_autopilot_stage(failed_stage, "")


def _job_message_label(session, job: Job, project: Project | None) -> str:
    raw = str(getattr(job, "message", "") or "").strip()
    if not raw:
        return ""
    status = _normalize(job.status)
    main = _main_stage_label(session, job, project)
    sub = _substage_label(session, job, project)
    if status == "queued":
        return f"{main}已加入队列，请稍候。" if main else "任务已加入队列，请稍候。"
    if status == "paused":
        return f"{main}已暂停。" if main else "任务已暂停。"
    if status == "cancelled":
        return f"{main}已取消。" if main else "任务已取消。"
    if status == "done":
        if sub == "渲染完成":
            return "任务已完成。"
        if main and sub:
            return f"{main}已完成，当前结果：{sub}。"
        if main:
            return f"{main}已完成。"
    if status == "running":
        if main and sub:
            return f"正在执行{main}，当前进度：{sub}。"
        if main:
            return f"正在执行{main}。"
    return raw


def _human_hint(session, job: Job, project: Project | None) -> str:
    payload = _parse_payload(job)
    message = str(getattr(job, "message", "") or "")
    kind = _normalize(job.kind)
    if kind == "autopilot" and _normalize(payload.get("current_stage")) == "render":
        sub = _label_render_substage(payload.get("render_substage"), "")
        if sub:
            return f"当前正在渲染子阶段：{sub}。"
    if _normalize(job.status) != "failed":
        return ""
    failed_summary = _failed_stage_summary(session, job, project)
    meta = job_error_meta(job)
    action = _normalize(meta.get("recommended_action"))
    if failed_summary and action == "continue_from_project":
        return f"失败发生在：{failed_summary}。回到项目页后，系统会从这一段附近继续处理。"
    if failed_summary and _needs_tts(job):
        return f"失败发生在：{failed_summary}。去“设置 -> 配音”检查当前配音方式和网络后重试。"
    if failed_summary and _needs_media(job):
        return f"失败发生在：{failed_summary}。建议先修复当前画面准备配置后重试。"
    if failed_summary and _needs_llm(job):
        return f"失败发生在：{failed_summary}。建议先检查大模型配置后重试。"
    if action == "go_settings_llm":
        return "大模型配置不可用：去“设置 -> 大模型”检查默认服务、服务地址、接口密钥和模型名称后重试。"
    if action == "go_settings_media":
        return "素材来源不可用：去“设置 -> 素材来源”检查素材服务配置，或先手动导入素材。"
    if action == "go_settings_tts":
        return "配音或字幕阶段失败：去“设置 -> 配音”检查当前配音方式和网络后重试。"
    if action == "continue_from_project":
        return "这个任务可回到项目页继续处理，系统会从失败阶段继续。"
    if "最终成片" in message or "渲染" in message:
        return "渲染没有产出最终成片：回到项目页继续生成视频时，系统会优先复用已完成的素材、配音和静音视频轨。"
    return "执行失败了：可先打开项目页查看当前状态和修复建议，再按建议处理后重试。"


def _stage_resume_label(job: Job) -> str:
    payload = _parse_payload(job)
    stage = _label_autopilot_stage(payload.get("resume_from_stage") or payload.get("last_failed_stage"), "")
    sub = _label_render_substage(payload.get("render_substage"), "")
    return " / ".join([part for part in (stage, sub) if part])


def _material_mode_label(material_mode: str) -> str:
    return "AI 镜头图" if _normalize(material_mode) == "ai" else "联网素材"


def _status_tone(status: str | None) -> str:
    normalized = _normalize(status)
    if normalized in {"failed", "cancelled"}:
        return "danger"
    if normalized == "done":
        return "success"
    if normalized == "paused":
        return "warning"
    return "info"


def _open_path(project_id: int, material_mode: str) -> str:
    return f"/p/ai/{project_id}" if _normalize(material_mode) == "ai" else f"/p/network/{project_id}"


def _project_delete_blocked(status: str | None) -> bool:
    return _normalize(status) == "running"


def _project_card_tone(summary_status: str | None, active_status: str | None, final_exists: bool, missing_asset_count: int, emphasize_asset_issues: bool) -> str:
    status = _normalize(summary_status or active_status)
    if status == "failed":
        return "danger"
    if status in ACTIVE_JOB_STATUSES:
        return "warning"
    if missing_asset_count > 0 and emphasize_asset_issues:
        return "warning"
    if final_exists:
        return "success"
    return ""


def _project_display_job(project_jobs: list[Job]) -> tuple[Job | None, JobChain | None, bool]:
    chains = _build_job_chains(project_jobs)
    chain = chains[0] if chains else None
    job = chain.head if chain else None
    is_active = bool(job and _normalize(job.status) in ACTIVE_JOB_STATUSES)
    return job, chain, is_active


def _project_notice(session, project: Project, material_mode: str, summary, continue_stage: str, final_exists: bool, missing_asset_count: int, emphasize_asset_issues: bool, display_job: Job | None, current_job_is_active: bool) -> str:
    if display_job and _normalize(display_job.status) == "failed":
        failed_at = _failed_stage_summary(session, display_job, project)
        hint = _human_hint(session, display_job, project)
        return "".join([part for part in (f"失败发生在：{failed_at}。" if failed_at else "", hint) if part]) or "最近一次生成失败，打开项目可继续处理。"
    if current_job_is_active and display_job:
        return _human_hint(session, display_job, project) or _job_message_label(session, display_job, project) or "项目状态正常，可打开项目查看并处理。"
    if missing_asset_count > 0 and emphasize_asset_issues:
        suffix = "缺镜头图" if material_mode == "ai" else "缺素材"
        return f"还有 {missing_asset_count} 个镜头{suffix}，建议进入“画面准备”补齐。"
    if continue_stage:
        return f"当前可从{_label_autopilot_stage(continue_stage, '当前阶段')}继续。"
    if final_exists:
        return "最终成片已生成，可打开项目查看，也可直接查看成片。"
    return "项目状态正常，可打开项目查看并处理。"


def _build_project_center_item(session, project: Project, project_jobs: list[Job]) -> ProjectCenterItemOut:
    project_id = int(project.id or 0)
    material_mode = project_material_mode(project)
    summary, _quality = project_summary_and_quality(session, project, latest_autopilot_job=latest_autopilot_job, autopilot_continue_stage=autopilot_continue_stage)
    wf_meta = get_project_workflow_meta(session, project)
    display_job, chain, current_job_is_active = _project_display_job(project_jobs)
    missing_asset_count = int(summary.missing_asset_count or 0)
    final_exists = bool(summary.final_exists)
    continue_stage = str(wf_meta.get("continue_stage") or summary.continue_stage or "")
    display_stage = _normalize(getattr(display_job, "current_stage", "")) if display_job else ""
    emphasize_asset_issues = (not current_job_is_active) or display_stage in {"", "media", "render"}
    tags = [FeedTagOut(label=str(project.channel_key or ""), type="info")]
    display_status = _normalize(display_job.status if display_job else summary.last_job_status)
    if display_status in {"running", "queued"}:
        tags.append(FeedTagOut(label="执行中", type="warning"))
    if display_status == "paused":
        tags.append(FeedTagOut(label="已暂停", type="warning"))
    if display_status == "failed":
        tags.append(FeedTagOut(label="执行失败", type="danger"))
    if missing_asset_count > 0 and emphasize_asset_issues:
        tags.append(FeedTagOut(label=f"{'缺镜头图' if material_mode == 'ai' else '缺素材'} {missing_asset_count}", type="danger"))
    if final_exists:
        tags.append(FeedTagOut(label="已有成片", type="success"))
    action_key = "open_project"
    action_label = "打开项目"
    if display_job and not current_job_is_active and _normalize(display_job.status) == "failed" and continue_stage:
        action_key = "continue_project"
        action_label = "继续生成视频"
    elif display_job and not current_job_is_active and _normalize(display_job.kind) == "autopilot" and _normalize(display_job.status) in {"failed", "cancelled"}:
        action_key = "rerun_project"
        action_label = "重新生成"
    return ProjectCenterItemOut(
        project_id=project_id,
        title=str(project.title or ""),
        workflow=str(getattr(project, "workflow", "mix") or "mix"),
        channel_key=str(project.channel_key or ""),
        material_mode=material_mode,
        material_mode_label=_material_mode_label(material_mode),
        open_path=_open_path(project_id, material_mode),
        tone=_project_card_tone(summary.last_job_status, wf_meta.get("active_job_status"), final_exists, missing_asset_count, emphasize_asset_issues),
        status=str(display_job.status if display_job else (wf_meta.get("active_job_status") or summary.last_job_status or project.status) or ""),
        status_label=_label_status(display_job.status if display_job else (wf_meta.get("active_job_status") or summary.last_job_status or project.status)),
        stage_text=_main_stage_label(session, display_job, project) if display_job else _label_autopilot_stage(wf_meta.get("workflow_stage") or summary.last_job_stage, "未开始"),
        notice=_project_notice(session, project, material_mode, summary, continue_stage, final_exists, missing_asset_count, emphasize_asset_issues, display_job, current_job_is_active),
        action_key=action_key,
        action_label=action_label,
        tags=tags,
        final_exists=final_exists,
        emphasize_asset_issues=emphasize_asset_issues,
        missing_asset_label="缺镜头图" if material_mode == "ai" else "缺素材",
        missing_asset_count=missing_asset_count,
        duplicate_asset_count=int(summary.duplicate_asset_count or 0),
        continue_stage_label=_label_autopilot_stage(continue_stage, "") if continue_stage else "",
        needs_llm_settings=bool(display_job and _normalize(display_job.status) == "failed" and _needs_llm(display_job)),
        needs_media_settings=bool(display_job and _normalize(display_job.status) == "failed" and _needs_media(display_job)),
        needs_tts_settings=bool(display_job and _normalize(display_job.status) == "failed" and _needs_tts(display_job)),
        can_delete=not _project_delete_blocked(display_job.status if display_job else wf_meta.get("active_job_status")),
        updated_at=project.updated_at,
        updated_at_text=_format_time(project.updated_at),
        current_job=(
            ProjectFeedJobOut(
                id=int(display_job.id or 0),
                kind=str(display_job.kind or ""),
                kind_label=_label_job_kind(display_job.kind),
                status=str(display_job.status or ""),
                status_label=_label_status(display_job.status),
                progress=int(display_job.progress or 0),
                stage_label=_main_stage_label(session, display_job, project),
                substage_label=_substage_label(session, display_job, project),
                stage_summary=_stage_summary(session, display_job, project),
                message_label=_job_message_label(session, display_job, project),
                hint=_human_hint(session, display_job, project),
                updated_at=display_job.updated_at,
                updated_at_text=_format_time(display_job.updated_at),
                resume_label=_stage_resume_label(display_job),
                chain_attempts_label=_chain_attempts_label(chain),
            )
            if display_job
            else None
        ),
        current_job_is_active=current_job_is_active,
    )


def _build_job_center_items(session, jobs: list[Job], *, scope: str = 'project', status: str = 'all', project_id: int = 0) -> list[JobCenterItemOut]:
    filtered_jobs = list(jobs)
    if scope == 'project':
        filtered_jobs = [job for job in filtered_jobs if _normalize(job.kind) in PROJECT_JOB_KINDS]
    if project_id > 0:
        filtered_jobs = [job for job in filtered_jobs if int(getattr(job, 'project_id', 0) or 0) == project_id]
    if status == 'failed':
        filtered_jobs = [job for job in filtered_jobs if _normalize(job.status) == 'failed']
    elif status == 'done':
        filtered_jobs = [job for job in filtered_jobs if _normalize(job.status) == 'done']
    elif status == 'cancelled':
        filtered_jobs = [job for job in filtered_jobs if _normalize(job.status) == 'cancelled']
    elif status == 'active':
        filtered_jobs = [job for job in filtered_jobs if _normalize(job.status) in ACTIVE_JOB_STATUSES]

    project_ids = sorted({int(getattr(job, 'project_id', 0) or 0) for job in filtered_jobs if int(getattr(job, 'project_id', 0) or 0) > 0})
    projects = session.exec(select(Project).where(Project.id.in_(project_ids))).all() if project_ids else []
    project_map = {int(project.id): project for project in projects if project.id is not None}
    final_map = {pid: bool(resolve_final_export_status(session, pid).get('exists')) for pid in project_ids}

    autopilot_jobs = [job for job in filtered_jobs if _normalize(job.kind) == 'autopilot']
    non_autopilot_jobs = [job for job in filtered_jobs if _normalize(job.kind) != 'autopilot']
    chains = _build_job_chains(autopilot_jobs)
    items: list[JobCenterItemOut] = []

    for chain in chains:
        head = chain.head
        pid = int(getattr(head, 'project_id', 0) or 0)
        project = project_map.get(pid)
        material_mode = project_material_mode(project) if project else 'network'
        meta = job_error_meta(head)
        items.append(
            JobCenterItemOut(
                entry_key=f'chain-{chain.root_id}',
                entry_type='chain',
                project_id=pid,
                project_title=str(getattr(head, 'project_title', '') or (project.title if project else f'项目 #{pid}')),
                project_material_mode=material_mode,
                project_open_path=_open_path(pid, material_mode),
                project_final_exists=bool(final_map.get(pid, False)),
                status=str(head.status or ''),
                status_label=_label_status(head.status),
                status_tone=_status_tone(head.status),
                job_id=int(head.id or 0),
                root_job_id=_job_root_id(head),
                attempt_count=len(chain.nodes),
                chain_attempts_label=_chain_attempts_label(chain),
                job_kind=str(head.kind or ''),
                job_kind_label=_label_job_kind(head.kind),
                stage_label=_main_stage_label(session, head, project),
                substage_label=_substage_label(session, head, project),
                message_label=_job_message_label(session, head, project),
                human_hint=_human_hint(session, head, project),
                progress=int(head.progress or 0),
                updated_at=head.updated_at,
                updated_at_text=_format_time(head.updated_at),
                error_code=meta.get('error_code'),
                error_code_label=_label_error_code(meta.get('error_code')),
                blocking_component=meta.get('blocking_component'),
                blocking_component_label=_label_blocking_component(meta.get('blocking_component')),
                recommended_action=meta.get('recommended_action'),
                recommended_action_label=_label_recommended_action(meta.get('recommended_action')),
                is_active=_normalize(head.status) in ACTIVE_JOB_STATUSES,
                is_deletable=_normalize(head.status) not in ACTIVE_JOB_STATUSES,
                history=[
                    JobCenterHistoryItemOut(
                        job_id=int(node.id or 0),
                        execution_label=_autopilot_execution_label(node),
                        status=str(node.status or ''),
                        status_label=_label_status(node.status),
                        status_tone=_status_tone(node.status),
                        stage_label=_main_stage_label(session, node, project),
                        substage_label=_substage_label(session, node, project),
                        updated_at=node.updated_at,
                        updated_at_text=_format_time(node.updated_at),
                    )
                    for node in chain.nodes
                ],
            )
        )

    for job in non_autopilot_jobs:
        pid = int(getattr(job, 'project_id', 0) or 0)
        project = project_map.get(pid)
        material_mode = project_material_mode(project) if project else 'network'
        meta = job_error_meta(job)
        items.append(
            JobCenterItemOut(
                entry_key=f'job-{int(job.id or 0)}',
                entry_type='job',
                project_id=pid,
                project_title=str(getattr(job, 'project_title', '') or (project.title if project else (f'项目 #{pid}' if pid > 0 else '系统任务'))),
                project_material_mode=material_mode,
                project_open_path=_open_path(pid, material_mode) if pid > 0 else '/jobs',
                project_final_exists=bool(final_map.get(pid, False)),
                status=str(job.status or ''),
                status_label=_label_status(job.status),
                status_tone=_status_tone(job.status),
                job_id=int(job.id or 0),
                root_job_id=_job_root_id(job),
                attempt_count=1,
                chain_attempts_label='',
                job_kind=str(job.kind or ''),
                job_kind_label=_label_job_kind(job.kind),
                stage_label=_main_stage_label(session, job, project),
                substage_label=_substage_label(session, job, project),
                message_label=_job_message_label(session, job, project),
                human_hint=_human_hint(session, job, project),
                progress=int(job.progress or 0),
                updated_at=job.updated_at,
                updated_at_text=_format_time(job.updated_at),
                error_code=meta.get('error_code'),
                error_code_label=_label_error_code(meta.get('error_code')),
                blocking_component=meta.get('blocking_component'),
                blocking_component_label=_label_blocking_component(meta.get('blocking_component')),
                recommended_action=meta.get('recommended_action'),
                recommended_action_label=_label_recommended_action(meta.get('recommended_action')),
                is_active=_normalize(job.status) in ACTIVE_JOB_STATUSES,
                is_deletable=_normalize(job.status) not in ACTIVE_JOB_STATUSES,
                history=[],
            )
        )

    items.sort(key=lambda item: ((item.updated_at or now_utc()), item.job_id), reverse=True)
    return items


def _project_item_dict(item: ProjectCenterItemOut) -> dict:
    return item.model_dump(mode='json')


def _job_item_dict(item: JobCenterItemOut) -> dict:
    return item.model_dump(mode='json')


def _hydrate_project_item(payload_json: str) -> ProjectCenterItemOut | None:
    try:
        payload = json.loads(str(payload_json or '{}'))
        if not isinstance(payload, dict):
            return None
        return ProjectCenterItemOut.model_validate(payload)
    except Exception:
        return None


def _hydrate_job_item(payload_json: str) -> JobCenterItemOut | None:
    try:
        payload = json.loads(str(payload_json or '{}'))
        if not isinstance(payload, dict):
            return None
        return JobCenterItemOut.model_validate(payload)
    except Exception:
        return None


def refresh_project_projection(project_id: int) -> None:
    from app.db import session_scope

    with session_scope() as session:
        project = session.exec(select(Project).where(Project.id == int(project_id))).first()
        if not project or project.id is None:
            delete_project_projection(int(project_id))
            delete_job_projections(int(project_id))
            return
        project_jobs = session.exec(select(Job).where(Job.project_id == int(project_id)).order_by(desc(Job.updated_at), desc(Job.id))).all()
        item = _build_project_center_item(session, project, project_jobs)
        upsert_project_projection(int(project_id), _project_item_dict(item))
        job_items = _build_job_center_items(session, project_jobs, scope='all', status='all', project_id=int(project_id))
        replace_job_projections(int(project_id), [_job_item_dict(entry) for entry in job_items])


def refresh_project_projections(project_ids: list[int]) -> None:
    for project_id in sorted({int(pid) for pid in project_ids if int(pid) > 0}):
        refresh_project_projection(project_id)


def rebuild_all_projections() -> None:
    from app.db import session_scope

    with session_scope() as session:
        project_ids = [int(project_id) for project_id in session.exec(select(Project.id).where(Project.workflow == 'mix')).all() if project_id is not None]
    refresh_project_projections(project_ids)


def get_project_center_feed(*, session, limit: int = 200) -> ProjectCenterFeedOut:
    query = visible_project_query(select(Project).where(Project.workflow == "mix"))
    projects = session.exec(query.order_by(desc(Project.updated_at)).limit(limit)).all()
    jobs = session.exec(select(Job).where(Job.project_id.in_([int(project.id) for project in projects if project.id is not None])).order_by(desc(Job.updated_at), desc(Job.id))).all() if projects else []
    jobs_by_project: dict[int, list[Job]] = defaultdict(list)
    for job in jobs:
        pid = int(getattr(job, "project_id", 0) or 0)
        if pid > 0:
            jobs_by_project[pid].append(job)

    items: list[ProjectCenterItemOut] = []
    for project in projects:
        items.append(_build_project_center_item(session, project, jobs_by_project.get(int(project.id or 0), [])))

    stats = ProjectCenterStatsOut(
        all=len(items),
        running=sum(1 for item in items if _normalize(item.status) in ACTIVE_JOB_STATUSES),
        failed=sum(1 for item in items if _normalize(item.status) == "failed"),
        final_ready=sum(1 for item in items if item.final_exists),
    )
    return ProjectCenterFeedOut(stats=stats, items=items, server_time=now_utc())


def get_project_center_feed_from_projection(*, limit: int = 200, cursor: str = '') -> ProjectCenterFeedOut:
    rows = load_project_projection_rows(limit=limit, cursor=cursor)
    items = [item for item in (_hydrate_project_item(row.payload_json) for row in rows) if item is not None]
    if items:
        projected_ids = sorted({int(item.project_id) for item in items if int(item.project_id) > 0})
        if projected_ids:
            with session_scope() as session:
                existing_ids = {
                    int(project_id)
                    for project_id in session.exec(visible_project_query(select(Project.id).where(Project.id.in_(projected_ids)))).all()
                    if project_id is not None
                }
            stale_ids = [project_id for project_id in projected_ids if project_id not in existing_ids]
            if stale_ids:
                for project_id in stale_ids:
                    if current_principal() is None or bool(current_principal().get('is_admin')):
                        delete_project_projection(project_id)
                        delete_job_projections(project_id)
                items = [item for item in items if int(item.project_id) in existing_ids]
    items = items[:limit]
    stats = ProjectCenterStatsOut(
        all=len(items),
        running=sum(1 for item in items if _normalize(item.status) in ACTIVE_JOB_STATUSES),
        failed=sum(1 for item in items if _normalize(item.status) == 'failed'),
        final_ready=sum(1 for item in items if item.final_exists),
    )
    next_cursor = items[-1].updated_at.isoformat() if items else ""
    return ProjectCenterFeedOut(stats=stats, items=items, server_time=now_utc(), next_cursor=next_cursor)


def get_job_center_feed(*, session, limit: int = 200, scope: str = "project", status: str = "all", project_id: int = 0) -> JobCenterFeedOut:
    jobs = session.exec(select(Job).order_by(desc(Job.updated_at)).limit(limit)).all()
    items = _build_job_center_items(session, jobs, scope=scope, status=status, project_id=project_id)
    stats = JobCenterStatsOut(
        all=len(items),
        active=sum(1 for item in items if item.is_active),
        failed=sum(1 for item in items if _normalize(item.status) == "failed"),
        done=sum(1 for item in items if _normalize(item.status) == "done"),
        cancelled=sum(1 for item in items if _normalize(item.status) == "cancelled"),
    )
    return JobCenterFeedOut(stats=stats, items=items, server_time=now_utc())


def get_job_center_feed_from_projection(*, limit: int = 200, scope: str = 'project', status: str = 'all', project_id: int = 0, cursor: str = '') -> JobCenterFeedOut:
    rows = load_job_projection_rows(project_id=project_id, scope=scope, status=status, limit=limit, cursor=cursor)
    items = [item for item in (_hydrate_job_item(row.payload_json) for row in rows) if item is not None]
    if current_principal() is not None and not bool(current_principal().get('is_admin')):
        with session_scope() as session:
            allowed_ids = visible_project_ids(session, {int(item.project_id) for item in items if int(item.project_id or 0) > 0})
        items = [item for item in items if int(item.project_id or 0) in allowed_ids]
    items = items[:limit]
    stats = JobCenterStatsOut(
        all=len(items),
        active=sum(1 for item in items if item.is_active),
        failed=sum(1 for item in items if _normalize(item.status) == 'failed'),
        done=sum(1 for item in items if _normalize(item.status) == 'done'),
        cancelled=sum(1 for item in items if _normalize(item.status) == 'cancelled'),
    )
    next_cursor = items[-1].updated_at.isoformat() if items else ''
    return JobCenterFeedOut(stats=stats, items=items, server_time=now_utc(), next_cursor=next_cursor)
