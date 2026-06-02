from __future__ import annotations

from loguru import logger
from sqlmodel import select

from app.db import session_scope
from app.jobs import abort_if_job_cancelled, is_job_cancelled, update_job, wait_if_job_paused
from app.logging_setup import sanitize_log_text
from app.models import Scene
from app.project_paths import project_generated_dir, rel_to_projects_root
from app.tasks_image_flow import bind_generated_scene_asset, mark_scene_generate_failed, save_generated_scene_image
from app.tasks_image_prepare import prepare_image_generation


def generate_images_impl(
    *,
    job_id: int,
    project_id: int,
    scene_ids: list[int] | None,
    force: bool,
    get_default_image_provider,
    list_available_image_providers,
    get_image_api_key,
    get_pack,
    generate_scene_image_via_provider,
    guess_image_ext,
    should_generate_scene,
    manage_job_state: bool,
) -> None:
    prep = prepare_image_generation(
        session_scope=session_scope,
        project_id=project_id,
        scene_ids=scene_ids,
        force=force,
        get_default_image_provider=get_default_image_provider,
        list_available_image_providers=list_available_image_providers,
        get_image_api_key=get_image_api_key,
        get_pack=get_pack,
        should_generate_scene=should_generate_scene,
    )
    project = prep.project
    pid = prep.pid
    provider = prep.provider
    api_key = prep.api_key
    pack = prep.pack
    targets = prep.targets

    if not targets:
        if manage_job_state:
            update_job(job_id, status="done", progress=100, message="所有镜头已有图片，无需生成")
        else:
            update_job(job_id, progress=66, message="生成视频：所有镜头已有图片，无需重新生成")
        return

    total = len(targets)
    failures: list[str] = []

    for i, sc in enumerate(targets):
        wait_if_job_paused(job_id)
        if is_job_cancelled(job_id):
            update_job(job_id, status="cancelled", progress=100, message="已取消")
            return
        progress = 5 + int((i / max(1, total)) * 90)
        message = f"正在生成第 {i + 1}/{total} 个镜头图片" if manage_job_state else f"生成视频：正在生成第 {i + 1}/{total} 个镜头图片"
        update_job(job_id, progress=progress, message=message)
        try:
            with session_scope() as session:
                scene = session.exec(select(Scene).where(Scene.id == sc.id)).first()
                if not scene:
                    raise RuntimeError("Scene missing")

                image_bytes, mime, meta = generate_scene_image_via_provider(
                    session=session,
                    provider=provider,
                    api_key=api_key,
                    project=project,
                    pack=pack,
                    scene=scene,
                )

            out_path = save_generated_scene_image(
                pid=pid,
                scene_idx=sc.idx,
                image_bytes=image_bytes,
                mime=mime,
                meta=meta,
                project_generated_dir=project_generated_dir,
                rel_to_projects_root=rel_to_projects_root,
                guess_image_ext=guess_image_ext,
            )
            bind_generated_scene_asset(
                session_scope=session_scope,
                scene_id=int(sc.id),
                pid=pid,
                out_path=out_path,
                mime=mime,
                meta=meta,
                rel_to_projects_root=rel_to_projects_root,
            )
        except Exception as exc:
            detail = f"scene {sc.idx}: {exc}"
            failures.append(detail)
            mark_scene_generate_failed(
                session_scope=session_scope,
                scene_id=int(sc.id),
                error_message=str(exc),
                preserve_existing_asset=True,
            )

    if failures:
        message = "; ".join(failures)[:900]
        if manage_job_state:
            update_job(job_id, status="failed", progress=100, message=message)
        else:
            update_job(job_id, progress=66, message=f"生成视频：部分镜头生图失败，暂保留旧图。{message}"[:900])
            raise RuntimeError(message)
    else:
        if manage_job_state:
            update_job(job_id, status="done", progress=100, message="图片已生成")
        else:
            update_job(job_id, progress=66, message="生成视频：镜头图片已生成")


def generate_project_images_local(
    job_id: int,
    project_id: int,
    *,
    force: bool,
    generate_images_impl=None,
    manage_job_state: bool = True,
) -> None:
    if generate_images_impl is None:
        from app.tasks import generate_project_images_impl_local as generate_images_impl_local

        return generate_images_impl_local(
            job_id,
            project_id,
            force=force,
            generate_images_impl=generate_images_impl,
            manage_job_state=manage_job_state,
        )
    if abort_if_job_cancelled(job_id):
        return
    if manage_job_state:
        update_job(job_id, status="running", progress=1, message="正在生成镜头图片")
    try:
        generate_images_impl(job_id=job_id, project_id=project_id, scene_ids=None, force=force, manage_job_state=manage_job_state)
    except Exception as exc:
        logger.exception("generate_project_images failed job_id={} project_id={} error={}", job_id, project_id, sanitize_log_text(exc))
        if manage_job_state:
            update_job(job_id, status="failed", progress=100, message=f"出图失败：{exc}")
        else:
            raise


def generate_scene_image_local(
    job_id: int,
    scene_id: int,
    *,
    force: bool,
    generate_images_impl=None,
    manage_job_state: bool = True,
) -> None:
    if generate_images_impl is None:
        from app.tasks import generate_scene_image_impl_local as generate_scene_image_impl_local

        return generate_scene_image_impl_local(
            job_id,
            scene_id,
            force=force,
            generate_images_impl=generate_images_impl,
            manage_job_state=manage_job_state,
        )
    if abort_if_job_cancelled(job_id):
        return
    if manage_job_state:
        update_job(job_id, status="running", progress=1, message="正在生成镜头图片")
    try:
        with session_scope() as session:
            scene = session.exec(select(Scene).where(Scene.id == scene_id)).first()
            if not scene:
                if manage_job_state:
                    update_job(job_id, status="failed", progress=100, message="镜头不存在")
                return
            pid = int(scene.project_id)

        generate_images_impl(job_id=job_id, project_id=pid, scene_ids=[scene_id], force=force, manage_job_state=manage_job_state)
    except Exception as exc:
        logger.exception("generate_scene_image failed job_id={} scene_id={} error={}", job_id, scene_id, sanitize_log_text(exc))
        if manage_job_state:
            update_job(job_id, status="failed", progress=100, message=f"单镜头出图失败：{exc}")
        else:
            raise
