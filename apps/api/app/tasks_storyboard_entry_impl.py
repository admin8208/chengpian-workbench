from __future__ import annotations

import json

from loguru import logger
from sqlmodel import select

from app.db import session_scope
from app.jobs import (
    abort_if_job_cancelled,
    is_job_cancelled,
    is_job_cancelled_in_session,
    update_job,
    update_job_in_session,
    wait_if_job_paused,
)
from app.logging_setup import sanitize_log_text
from app.models import Scene
from app.time_utils import now_utc


def rewrite_storyboard_local(
    job_id: int,
    project_id: int,
    *,
    select_project,
    get_pack,
    fail_job,
    get_default_provider,
    get_api_key,
    llm_rewrite_storyboard,
) -> None:
    if abort_if_job_cancelled(job_id):
        return
    update_job(job_id, status="running", progress=1, message="正在洗稿并生成分镜（大模型）")
    wait_if_job_paused(job_id)
    try:
        with session_scope() as session:
            project = select_project(session, project_id)
            if not project:
                update_job(job_id, status="failed", progress=100, message="项目不存在")
                return
            if project.id is None:
                raise RuntimeError("project id missing")
            pid = int(project.id)

            pack = get_pack(session, project.channel_key)
            if not pack:
                update_job(job_id, status="failed", progress=100, message="频道内容包不存在")
                return
            src = (project.source_text or "").strip()
            if not src:
                fail_job(job_id, message="原文/要点为空", error_code="source_text_missing", blocking_component="project", recommended_action="open_project", recoverable=True)
                return

            provider = get_default_provider(session)
            if not provider or not provider.enabled or provider.id is None:
                fail_job(job_id, message="未配置默认大模型服务", error_code="llm_config_missing", blocking_component="llm", recommended_action="go_settings_llm", recoverable=True)
                return
            api_key = get_api_key(session, int(provider.id))
            character_profile = project.character_profile or ""
            render_cfg = project.render_config() if hasattr(project, "render_config") else {}
            workflow = getattr(project, "workflow", "mix") or "mix"

        update_job(job_id, progress=20, message="调用大模型")
        wait_if_job_paused(job_id)
        if is_job_cancelled(job_id):
            update_job(job_id, status="cancelled", progress=100, message="已取消")
            return
        script, scenes = llm_rewrite_storyboard(
            src,
            pack,
            provider,
            api_key,
            character_profile=character_profile,
            level="medium",
            workflow=workflow,
            render_cfg=render_cfg,
        )
        update_job(job_id, progress=70, message="保存分镜")

        with session_scope() as session:
            project = select_project(session, pid)
            if not project:
                update_job(job_id, status="failed", progress=100, message="项目不存在")
                return

            old = session.exec(select(Scene).where(Scene.project_id == pid)).all()
            for scene in old:
                session.delete(scene)

            project.script = script
            project.status = "processing"
            project.updated_at = now_utc()
            session.add(project)

            for i, scene_payload in enumerate(scenes):
                if is_job_cancelled_in_session(session, job_id):
                    update_job_in_session(session, job_id, status="cancelled", progress=100, message="已取消")
                    return
                sc = Scene(
                    project_id=pid,
                    idx=int(scene_payload["idx"]),
                    narration=scene_payload["narration"],
                    media_query=str(scene_payload.get("media_query") or scene_payload.get("narration") or "").strip()[:120],
                    image_prompt=scene_payload["image_prompt"],
                    image_negative=str(scene_payload.get("image_negative", "")),
                    duration_sec=float(scene_payload["duration_sec"]),
                    status="pending",
                )
                try:
                    meta = scene_payload.get("meta") if isinstance(scene_payload, dict) else None
                    if isinstance(meta, dict):
                        sc.meta_json = json.dumps(meta, ensure_ascii=True)
                except Exception:
                    pass
                session.add(sc)
                if i % 2 == 0:
                    update_job_in_session(session, job_id, progress=min(95, 70 + int((i + 1) / len(scenes) * 25)))

        update_job(job_id, status="done", progress=100, message="洗稿完成")
    except Exception as exc:
        logger.exception("rewrite_storyboard failed job_id={} project_id={} error={}", job_id, project_id, sanitize_log_text(exc))
        fail_job(job_id, message=f"洗稿失败：{exc}", error_code="storyboard_failed", blocking_component="llm", recommended_action="go_settings_llm", recoverable=True)


def generate_storyboard_local(
    job_id: int,
    project_id: int,
    *,
    topic: str | None,
    select_project,
    get_pack,
    fail_job,
    get_default_provider,
    get_api_key,
    llm_generate_storyboard,
) -> None:
    if abort_if_job_cancelled(job_id):
        return
    update_job(job_id, status="running", progress=1, message="正在生成脚本与分镜")
    wait_if_job_paused(job_id)
    try:
        with session_scope() as session:
            project = select_project(session, project_id)
            if not project or project.id is None:
                update_job(job_id, status="failed", progress=100, message="项目不存在")
                return
            pid = int(project.id)

            pack = get_pack(session, project.channel_key)
            if not pack:
                update_job(job_id, status="failed", progress=100, message="频道内容包不存在")
                return

            if topic:
                project.title = topic
                project.updated_at = now_utc()
                session.add(project)

            title = project.title
            character_profile = project.character_profile or ""
            render_cfg = project.render_config() if hasattr(project, "render_config") else {}
            workflow = getattr(project, "workflow", "mix") or "mix"
            provider = get_default_provider(session)
            api_key = ""
            if provider and provider.enabled and provider.id is not None:
                api_key = get_api_key(session, int(provider.id))

        if not provider or not provider.enabled:
            update_job(job_id, status="failed", progress=100, message="LLM 服务不可用，请检查配置")
            return

        update_job(job_id, progress=15, message="调用大模型")
        wait_if_job_paused(job_id)
        if is_job_cancelled(job_id):
            update_job(job_id, status="cancelled", progress=100, message="已取消")
            return
        try:
            script, scenes = llm_generate_storyboard(
                title,
                pack,
                provider,
                api_key,
                character_profile=character_profile,
                workflow=workflow,
                render_cfg=render_cfg,
            )
        except Exception as exc:
            update_job(job_id, status="failed", progress=100, message=f"LLM 调用失败: {exc}")
            return

        if not script or not scenes:
            update_job(job_id, status="failed", progress=100, message="LLM 生成结果为空")
            return

        update_job(job_id, progress=55, message="保存分镜")
        wait_if_job_paused(job_id)
        with session_scope() as session:
            project = select_project(session, pid)
            if not project:
                update_job(job_id, status="failed", progress=100, message="项目不存在")
                return

            project.script = script
            project.status = "processing"
            project.updated_at = now_utc()
            session.add(project)

            old = session.exec(select(Scene).where(Scene.project_id == pid)).all()
            for scene in old:
                session.delete(scene)

            for i, scene_payload in enumerate(scenes):
                if is_job_cancelled_in_session(session, job_id):
                    update_job_in_session(session, job_id, status="cancelled", progress=100, message="已取消")
                    return
                sc = Scene(
                    project_id=pid,
                    idx=int(scene_payload["idx"]),
                    narration=scene_payload["narration"],
                    media_query=str(scene_payload.get("media_query") or scene_payload.get("narration") or "").strip()[:120],
                    image_prompt=scene_payload["image_prompt"],
                    image_negative=str(scene_payload.get("image_negative", "")),
                    duration_sec=float(scene_payload["duration_sec"]),
                    status="pending",
                )
                try:
                    meta = scene_payload.get("meta") if isinstance(scene_payload, dict) else None
                    if isinstance(meta, dict):
                        sc.meta_json = json.dumps(meta, ensure_ascii=True)
                except Exception:
                    pass
                session.add(sc)
                if i % 2 == 0:
                    update_job_in_session(session, job_id, progress=min(90, 55 + int((i + 1) / len(scenes) * 35)))

        update_job(job_id, status="done", progress=100, message="分镜已生成")
    except Exception as exc:
        logger.exception("generate_storyboard failed job_id={} project_id={} error={}", job_id, project_id, sanitize_log_text(exc))
        fail_job(job_id, message=f"分镜生成失败：{exc}", error_code="storyboard_failed", blocking_component="llm", recommended_action="go_settings_llm", recoverable=True)
