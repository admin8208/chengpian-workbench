from pathlib import Path

from sqlmodel import select

from app.time_utils import now_utc


def finalize_render_output_bundle(
    *,
    is_job_cancelled,
    target_job_id: int,
    out_tmp: Path,
    mark_render_substage,
    finalize_render_outputs,
    pid: int,
    tag: str,
    ts: str,
    out_dir: Path,
    out_file: Path,
    audio_path: Path,
    srt_path: Path,
    candidate_batch_id: str | None,
    render_token: str,
    render_meta: dict | None,
    on_cancel,
):
    if is_job_cancelled(target_job_id):
        try:
            out_tmp.unlink(missing_ok=True)
        except Exception:
            pass
        on_cancel()
        return None

    mark_render_substage("finalize_output")
    return finalize_render_outputs(
        pid=pid,
        tag=tag,
        ts=ts,
        out_dir=out_dir,
        out_file=out_file,
        out_tmp=out_tmp,
        audio_path=audio_path,
        srt_path=srt_path,
        candidate_batch_id=candidate_batch_id,
        render_job_id=int(target_job_id),
        render_token=render_token,
        render_meta=render_meta,
    )


def mark_project_ready_if_export(*, tag: str, project_id: int, session_scope, project_model) -> None:
    if tag != "export":
        return
    with session_scope() as session:
        project = session.exec(select(project_model).where(project_model.id == project_id)).first()
        if project:
            project.status = "ready"
            project.updated_at = now_utc()
            session.add(project)


def cleanup_non_cached_silent_track(silent_path: Path | None) -> None:
    try:
        if silent_path and silent_path.exists() and silent_path.is_file() and not silent_path.name.startswith("silent_cache_"):
            silent_path.unlink(missing_ok=True)
    except Exception:
        pass
