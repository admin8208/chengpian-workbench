import json
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import desc
from sqlmodel import Session, select

from app.access_control import require_project_access
from app.api_common import get_project_workflow_meta, job_error_meta, resolve_final_export_status
from app.db import session_scope
from app.jobs import get_job_payload
from app.models import Asset, Job, Project, Scene
from app.modules.creator.project_autopilot_service import continue_autopilot_api, rerun_autopilot_api, start_autopilot_api
from app.modules.creator.project_deletion_service import delete_project_api
from app.modules.creator.project_mutation_service import create_project_api, patch_project_api, validate_render_config
from app.modules.creator.project_queries import list_projects_api
from app.modules.creator.project_script_service import confirm_project_script_api, prepare_project_script_api, start_prepare_project_script_job_api
from app.modules.pipeline.repository import get_pipeline_run
from app.modules.pipeline.state import normalize_autopilot_stage
from app.modules.project_summary.resolver import resolve_project_summary_strategy
from app.modules.tts.service import tts_status_dict
from app.project_summary_metrics import (
    content_reasonability_metrics,
    duplicate_scene_asset_ids,
    subtitle_style_label,
    summary_continuity_metrics,
    summary_main_clip_metrics,
    tts_backend_label,
)
from app.schemas import JobOut, ProjectDetailOut, ProjectQualityOut, ProjectRuntimeOut, ProjectSummaryOut
from app.settings import settings
from app.subtitles import normalize_subtitle_settings
from app.tasks_autopilot import project_material_mode


def runtime_job_out(job: Job | None, project: Project | None = None) -> JobOut | None:
    if not job or job.id is None:
        return None
    meta = job_error_meta(job)
    return JobOut(
        id=int(job.id),
        kind=str(job.kind or ""),
        project_id=int(job.project_id or 0),
        parent_job_id=(int(job.parent_job_id) if getattr(job, "parent_job_id", None) is not None else None),
        root_job_id=(int(job.root_job_id) if getattr(job, "root_job_id", None) is not None else None),
        retry_seq=int(getattr(job, "retry_seq", 0) or 0),
        project_title=((str(getattr(project, "title", "") or "").strip()) or None) if project else None,
        project_workflow=((str(getattr(project, "workflow", "") or "").strip()) or None) if project else None,
        status=str(job.status or ""),
        progress=int(job.progress or 0),
        message=str(job.message or ""),
        payload_json=job.payload_json or "{}",
        cancel_requested=bool(getattr(job, "cancel_requested", False)),
        pause_requested=bool(getattr(job, "pause_requested", False)),
        cancel_source=str(getattr(job, "cancel_source", "") or ""),
        cancel_reason=str(getattr(job, "cancel_reason", "") or ""),
        worker_id=str(getattr(job, "worker_id", "") or ""),
        worker_pid=int(getattr(job, "worker_pid", 0) or 0),
        worker_started_at=getattr(job, "worker_started_at", None),
        worker_heartbeat_at=getattr(job, "worker_heartbeat_at", None),
        error_code=meta.get("error_code"),
        blocking_component=meta.get("blocking_component"),
        recommended_action=meta.get("recommended_action"),
        recoverable=meta.get("recoverable"),
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


def get_project_detail_api(project_id: int, *, scene_to_out, project_to_out) -> ProjectDetailOut:
    with session_scope() as session:
        p = require_project_access(session, project_id)
        base = project_to_out(session, p)
        scenes = session.exec(select(Scene).where(Scene.project_id == int(p.id)).order_by(Scene.idx)).all()
        return ProjectDetailOut(**base.model_dump(), scenes=[scene_to_out(session, s) for s in scenes])


def get_project_runtime_api(
    project_id: int,
    *,
    project_summary_and_quality_cb,
) -> ProjectRuntimeOut:
    with session_scope() as session:
        p = require_project_access(session, project_id)
        summary, _quality = project_summary_and_quality_cb(session, p)
        wf_meta = get_project_workflow_meta(session, p)
        summary_job = wf_meta.get("summary_job")
        current_job = session.exec(
            select(Job)
            .where(Job.project_id == int(project_id))
            .where(Job.status.in_(["queued", "running", "paused"]))
            .order_by(desc(Job.created_at))
        ).first()

        blocker_items: list[str] = []
        active_status = str(wf_meta.get("active_job_status") or "").strip().lower()
        if active_status == "queued":
            blocker_items.append("当前有排队中的任务")
        elif active_status == "running":
            blocker_items.append("当前有运行中的任务")
        elif active_status == "paused":
            blocker_items.append("当前有暂停中的任务")
        material_mode = project_material_mode(p)
        summary_strategy = resolve_project_summary_strategy(material_mode)
        if int(summary.missing_asset_count or 0) > 0:
            blocker_items.append(f"还有 {int(summary.missing_asset_count)} 个镜头{summary_strategy.blocker_missing_asset_label()}")
        if str(summary.last_job_status or "").strip().lower() == "failed" and summary.continue_stage:
            blocker_items.append(f"最近一次生成失败，可从 {summary.continue_stage} 继续")

        return ProjectRuntimeOut(
            project_id=int(project_id),
            project_title=str(p.title or ""),
            workflow=str(getattr(p, "workflow", "mix") or "mix"),
            material_mode=material_mode,
            project_status=str(p.status or "draft"),
            confirmed_baseline_revision_id=getattr(p, "confirmed_baseline_revision_id", None),
            current_pipeline_run_id=getattr(p, "current_pipeline_run_id", None),
            workflow_stage=wf_meta.get("workflow_stage") or summary.last_job_stage,
            continue_stage=wf_meta.get("continue_stage") or summary.continue_stage,
            active_job_status=wf_meta.get("active_job_status") or summary.last_job_status,
            next_action=str(wf_meta.get("next_action") or "open_project"),
            last_job_kind=summary.last_job_kind,
            last_job_status=summary.last_job_status,
            last_job_message=summary.last_job_message,
            final_exists=bool(summary.final_exists),
            missing_asset_count=int(summary.missing_asset_count or 0),
            review_count=0,
            duplicate_asset_count=int(summary.duplicate_asset_count or 0),
            blocker_items=blocker_items[:6],
            suggested_fix_actions=list(summary.fix_actions or [])[:6],
            summary_suggestions=list(summary.suggestions or [])[:6],
            current_job=runtime_job_out(current_job, p),
            summary_job=runtime_job_out(summary_job, p),
        )


def project_summary_and_quality(
    session: Session,
    project: Project,
    *,
    latest_autopilot_job,
    autopilot_continue_stage,
) -> tuple[ProjectSummaryOut, ProjectQualityOut]:
    pid = int(project.id or 0)
    scenes = session.exec(select(Scene).where(Scene.project_id == pid).order_by(Scene.idx)).all()
    assets = session.exec(select(Asset).where(Asset.project_id == pid)).all()
    latest_job = session.exec(select(Job).where(Job.project_id == pid).order_by(desc(Job.created_at))).first()
    active_job = session.exec(select(Job).where(Job.project_id == pid).where(Job.status.in_(["queued", "running", "paused"])).order_by(desc(Job.created_at))).first()
    latest_autopilot = latest_autopilot_job(session, pid, active_only=False)
    active_autopilot = latest_autopilot_job(session, pid, active_only=True)
    summary_job = active_job or active_autopilot or latest_autopilot or latest_job
    pipeline_run = get_pipeline_run(session, getattr(project, "current_pipeline_run_id", None))
    summary_payload = get_job_payload(int(summary_job.id)) if summary_job and summary_job.id is not None else {}
    summary_stage = str(getattr(pipeline_run, "current_stage", "") or summary_payload.get("current_stage") or summary_payload.get("last_failed_stage") or "").strip().lower() or None
    continue_stage = normalize_autopilot_stage(getattr(pipeline_run, "resume_from_stage", "")) or autopilot_continue_stage(summary_payload)

    rcfg = project.render_config() if hasattr(project, "render_config") else {}
    subtitle_style, subtitle_effective = normalize_subtitle_settings(
        str((rcfg or {}).get("subtitle_style") or "boxed").strip().lower() or "boxed",
        {
            "font_name": (rcfg or {}).get("subtitle_font_name"),
            "font_size": (rcfg or {}).get("subtitle_font_size"),
            "position": (rcfg or {}).get("subtitle_position"),
            "outline": (rcfg or {}).get("subtitle_outline"),
            "margin_v": (rcfg or {}).get("subtitle_margin_v"),
            "boxed": (rcfg or {}).get("subtitle_boxed"),
            "height": (rcfg or {}).get("height"),
        },
    )

    missing_asset_count = 0
    review_count = 0
    bound_asset_ids: list[int] = []
    for sc in scenes:
        if not getattr(sc, "image_asset_id", None):
            missing_asset_count += 1
        else:
            try:
                aid = int(sc.image_asset_id)
                bound_asset_ids.append(aid)
            except Exception:
                pass
        try:
            json.loads(getattr(sc, "meta_json", "{}") or "{}")
        except Exception:
            pass

    duplicate_scene_ids = duplicate_scene_asset_ids(scenes)
    duplicate_asset_count = len(duplicate_scene_ids)
    final_status = resolve_final_export_status(session, pid)
    export_count = 0
    try:
        export_count = len([a for a in assets if str(a.kind or "") == "video" and str(a.tag or "") == "export"])
    except Exception:
        export_count = 0
    final_exists = bool(final_status.get("exists"))
    final_size = int(final_status.get("size") or 0)
    proj_dir = settings.data_dir / "projects" / f"project_{pid}" / "exports"
    try:
        hist_dir = proj_dir / "history"
        history_count = len([p for p in hist_dir.glob("*.mp4") if p.is_file()]) if hist_dir.exists() else 0
    except Exception:
        history_count = 0
    try:
        tts_backend = str(tts_status_dict(session=session).get("backend") or "auto")
    except Exception:
        tts_backend = "auto"
    material_mode = project_material_mode(project)
    summary_strategy = resolve_project_summary_strategy(material_mode)
    input_mode = str((project.render_config() if hasattr(project, "render_config") else {}).get("input_mode") or "text").strip().lower() or "text"

    strengths: list[str] = []
    issues: list[str] = []
    suggestions: list[str] = []
    fix_actions: list[str] = []
    score = 100
    if final_exists:
        strengths.append("已生成稳定最终成片 final.mp4")
    else:
        score -= 25
        issues.append("还没有最终成片")
        suggestions.append("先运行生成视频或仅渲染，生成 stable final.mp4")
        fix_actions.append("render")
    subtitle_asset_ext = ""
    try:
        if getattr(project, "subtitle_asset_id", None):
            sub_a = session.exec(select(Asset).where(Asset.id == project.subtitle_asset_id)).first()
            if sub_a:
                subtitle_asset_ext = str(Path(str(sub_a.rel_path or "")).suffix or "").strip().lower()
    except Exception:
        subtitle_asset_ext = ""
    if missing_asset_count > 0:
        score -= min(20, missing_asset_count * 4)
        issues.append(summary_strategy.missing_asset_message(missing_asset_count))
        suggestions.append(summary_strategy.missing_asset_suggestion())
        fix_actions.append(summary_strategy.missing_asset_fix_action())
    else:
        mode_strength, coverage_strength = summary_strategy.mode_strength_labels()
        strengths.append(mode_strength)
        strengths.append(coverage_strength)
    if duplicate_asset_count >= 2:
        score -= min(10, duplicate_asset_count * 2)
        duplicate_issue, duplicate_suggestion, duplicate_fix_action = summary_strategy.duplicate_asset_feedback()
        issues.append(duplicate_issue)
        suggestions.append(duplicate_suggestion)
        fix_actions.append(duplicate_fix_action)
    continuity = summary_continuity_metrics(scenes)
    anchor_coverage = float(continuity.get("anchor_coverage") or 0.0)
    jump_rate = float(continuity.get("adjacent_jump_rate") or 0.0)
    main_clip = summary_main_clip_metrics(scenes)
    main_clip_count = int(main_clip.get("main_clip_count") or 0)
    main_clip_coverage = int(main_clip.get("main_clip_coverage") or 0)
    if main_clip_count > 0:
        strengths.append(f"主素材模式：{main_clip_count} 条主视频覆盖约 {main_clip_coverage}% 时长")
    if str(getattr(project, "channel_key", "") or "").strip().lower() == "emotion":
        if main_clip_count > 1:
            suggestions.append("情感频道建议优先单主素材，必要时再回退第二条，减少拼盘感")
        if main_clip_coverage < 60:
            suggestions.append("主素材覆盖偏低，建议在混合模式下补一条更长、意境一致的主视频")
    if anchor_coverage < 0.6:
        score -= 8
        continuity_issue, continuity_suggestion = summary_strategy.continuity_feedback(anchor_coverage=anchor_coverage, jump_rate=0.0) or (f"视觉主线不稳定（锚点覆盖率 {int(anchor_coverage * 100)}%）", "建议先处理问题镜头后再重渲染")
        issues.append(continuity_issue)
        suggestions.append(continuity_suggestion)
        fix_actions.append("focus_scene_issues")
    if jump_rate > 0.2:
        score -= 8
        continuity_issue, continuity_suggestion = summary_strategy.continuity_feedback(anchor_coverage=1.0, jump_rate=jump_rate) or (f"相邻镜头跳变偏多（跳变率 {int(jump_rate * 100)}%）", "建议先处理问题镜头再重渲染")
        issues.append(continuity_issue)
        suggestions.append(continuity_suggestion)
        fix_actions.append("focus_scene_issues")
    if tts_backend == "offline_piper":
        strengths.append("离线配音可用，弱网环境也能稳定出片")
    elif tts_backend == "edge":
        strengths.append("当前默认使用微软 TTS，语音质感更自然")
    subtitle_safe = subtitle_style == "boxed" and str(subtitle_effective.get("position") or "bottom") == "bottom" and 18 <= int(subtitle_effective.get("font_size") or 22) <= 48
    if subtitle_asset_ext in (".ass", ".vtt"):
        subtitle_safe = False
    if subtitle_safe:
        strengths.append("字幕风格已锁定为电影黑底样式")
    else:
        issues.append("字幕配置仍可能沿用旧覆盖值，观感未完全收敛")
        suggestions.append("建议重置字幕为安全默认：底部、电影黑底字幕、主流字号")
        if subtitle_asset_ext in (".ass", ".vtt"):
            suggestions.append("上传的字幕文件不是标准 SRT，建议改为 SRT 或让系统重新生成，以保证稳定字幕样式")
    if summary_job and str(summary_job.status or "") == "failed":
        score -= 8
        issues.append("最近一次任务失败，建议先按失败提示修复后重试")
        if str(getattr(summary_job, "kind", "") or "") == "autopilot" and continue_stage:
            fix_actions.append("continue_from_project")
        else:
            fix_actions.append("render")
        last_msg = str(summary_job.message or "")
        if any(x in last_msg for x in ("大模型", "Provider", "model", "base_url")):
            fix_actions.append("go_settings_llm")
        media_settings_action = summary_strategy.media_settings_fix_action(last_msg)
        if media_settings_action:
            fix_actions.append(media_settings_action)
        if any(x in last_msg for x in ("Edge TTS", "配音", "字幕")):
            fix_actions.append("go_settings_tts")
    reasonability = content_reasonability_metrics(project, scenes)
    reasonability_score = int(reasonability.get("score") or 0)
    reasonability_items = [str(x).strip() for x in (reasonability.get("items") or []) if str(x).strip()]
    reasonability_metrics = reasonability.get("metrics") if isinstance(reasonability.get("metrics"), dict) else {}
    if reasonability_score < 75:
        reasonability_suggestion, reasonability_fix_action = summary_strategy.reasonability_feedback()
        suggestions.append(reasonability_suggestion)
        fix_actions.append(reasonability_fix_action)
    score = max(0, min(100, score))
    if not suggestions:
        suggestions.append(summary_strategy.default_summary_suggestion())
    metrics = {
        "material_coverage": max(0, min(100, int(round((1.0 - (missing_asset_count / max(1, len(scenes)))) * 100.0)))),
        "material_match": max(0, min(100, 100 - duplicate_asset_count * 3)),
        "subtitle_readability": 96 if subtitle_safe else 72,
        "voice_stability": 90 if tts_backend in ("edge", "offline_piper") else 72,
        "edit_rhythm": max(55, min(96, 92 - duplicate_asset_count * 7)),
        "visual_continuity": max(0, min(100, int(round(anchor_coverage * 100.0 - jump_rate * 40.0)))),
        "main_clip_count": max(0, main_clip_count),
        "main_clip_coverage": max(0, min(100, main_clip_coverage)),
    }
    base_publish_title = str(project.publish_title or project.title or "").strip()
    base_tags = str(project.publish_hashtags or "").strip()
    platform_notes = {
        "douyin": ["抖音更适合前 3 秒直接给冲突点或结果。", f"标题建议压短到 18 字内：{base_publish_title[:18] if base_publish_title else '先给结果，再补原因'}", "字幕保持底部短视频大字即可，不要铺满整屏。"],
        "shipinhao": ["视频号更适合信息完整、语气稳一点的版本。", f"标题可稍完整：{base_publish_title[:24] if base_publish_title else '把结论和价值点写清楚'}", "建议优先使用稳妥版或质感版候选。"],
        "xiaohongshu": ["小红书更看重封面和标题的生活感/经验感。", f"可补一个经验型标题：{base_publish_title[:16] if base_publish_title else '我用这个方法后，真的省了很多时间'}", f"话题建议控制在 3-5 个：{base_tags[:28] if base_tags else '#经验分享 #干货 #避坑'}"],
    }
    suggestions = list(dict.fromkeys([str(x).strip() for x in suggestions if str(x).strip()]))
    fix_actions = list(dict.fromkeys([str(x).strip() for x in fix_actions if str(x).strip()]))
    pipeline_status = str(getattr(pipeline_run, "status", "") or "").strip().lower()
    summary = ProjectSummaryOut(project_id=pid, project_title=str(project.title or ""), workflow=str(getattr(project, "workflow", "mix") or "mix"), status=str(project.status or "draft"), confirmed_baseline_revision_id=getattr(project, "confirmed_baseline_revision_id", None), current_pipeline_run_id=getattr(project, "current_pipeline_run_id", None), input_mode=("audio" if input_mode == "audio" else "text"), scene_count=len(scenes), missing_asset_count=missing_asset_count, review_count=0, duplicate_asset_count=duplicate_asset_count, final_exists=bool(final_exists), final_size=final_size, history_count=history_count, export_count=export_count, tts_backend=tts_backend, tts_backend_label=tts_backend_label(tts_backend), subtitle_style=subtitle_style, subtitle_style_label=subtitle_style_label(subtitle_style), last_job_kind=(str(summary_job.kind) if summary_job else None), last_job_status=(pipeline_status or (str(summary_job.status) if summary_job else None)), last_job_message=(str(summary_job.message) if summary_job else None), last_job_stage=summary_stage, continue_stage=continue_stage, suggestions=suggestions[:6], fix_actions=fix_actions[:8], content_reasonableness_score=reasonability_score, content_reasonableness_items=reasonability_items[:4], content_reasonableness_metrics={k: int(v) for k, v in reasonability_metrics.items() if isinstance(v, int)})
    summary.material_mode = material_mode
    quality = ProjectQualityOut(score=score, issues=issues[:6], strengths=strengths[:6], suggestions=suggestions[:6], metrics=metrics, platform_notes=platform_notes)
    return summary, quality


def get_project_summary_api(project_id: int, *, project_summary_and_quality_cb) -> ProjectSummaryOut:
    with session_scope() as session:
        p = require_project_access(session, project_id)
        summary, _quality = project_summary_and_quality_cb(session, p)
        return summary


def get_project_quality_api(project_id: int, *, project_summary_and_quality_cb) -> ProjectQualityOut:
    with session_scope() as session:
        p = require_project_access(session, project_id)
        _summary, quality = project_summary_and_quality_cb(session, p)
        return quality
