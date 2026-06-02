
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlmodel import select

from app.db import session_scope
from app.jobs import create_job
from app.modules.media.library_import import import_to_library
from app.llm_client import LlmChatMessage, ollama_chat_json, openai_compat_chat_json
from app.modules.media.service import get_media_api_key, has_media_api_key
from app.models import Asset, ChannelPack, Job, Project, Scene
from app.schemas import DoctorItemOut, DoctorOut
from app.modules.media.web_search import search_web_media
from app.time_utils import now_utc, utc_iso_z


def _now_iso() -> str:
    return utc_iso_z()


def _job_snapshot(job_id: int) -> tuple[str, int, str]:
    with session_scope() as session:
        j = session.exec(select(Job).where(Job.id == job_id)).first()
        if not j:
            return ("missing", 0, "")
        return (str(j.status or ""), int(j.progress or 0), str(j.message or ""))


def _delete_asset_file(a: Asset) -> None:
    # Best-effort only; DB rows can still be removed even if file delete fails.
    from app.settings import settings

    def _safe_unlink(base, rel: str) -> None:
        if not rel:
            return
        try:
            import pathlib

            b = pathlib.Path(str(base)).resolve()
            p = (b / str(rel).lstrip("/")).resolve()
            if b not in p.parents and p != b:
                return
            if p.exists() and p.is_file():
                p.unlink()
        except Exception:
            return

    if not a or not a.rel_path:
        return
    tag = str(a.tag or "").strip().lower()
    if a.kind == "video" and tag in ("export", "export_history"):
        _safe_unlink(settings.exports_dir, a.rel_path)
    else:
        _safe_unlink(settings.assets_dir, a.rel_path)


def _cleanup_doctor_project(*, project_id: int, started_at: datetime) -> None:
    """Delete doctor project and artifacts created during the run."""

    # Delete project-scoped assets + scenes + jobs (best-effort).
    with session_scope() as session:
        p = session.exec(select(Project).where(Project.id == project_id)).first()
        if p:
            # Only allow cleanup for doctor projects.
            if not str(p.title or "").startswith("__doctor__"):
                return

        # Delete assets that belong to the project (including export videos)
        assets = session.exec(select(Asset).where(Asset.project_id == project_id)).all()
        for a in assets:
            try:
                _delete_asset_file(a)
            except Exception:
                pass
            try:
                session.delete(a)
            except Exception:
                pass

        # Delete render folder (stable final.mp4) best-effort
        try:
            from app.settings import settings

            def _safe_rmtree(base, rel: str) -> None:
                if not rel:
                    return
                try:
                    import pathlib
                    import shutil

                    b = pathlib.Path(str(base)).resolve()
                    p = (b / str(rel).lstrip("/")).resolve()
                    if b not in p.parents and p != b:
                        return
                    if p.exists() and p.is_dir():
                        shutil.rmtree(p, ignore_errors=True)
                except Exception:
                    return

            _safe_rmtree(settings.exports_dir, f"project_{int(project_id)}")
        except Exception:
            pass

        scenes = session.exec(select(Scene).where(Scene.project_id == project_id)).all()
        for s in scenes:
            try:
                session.delete(s)
            except Exception:
                pass

        jobs = session.exec(select(Job).where(Job.project_id == project_id)).all()
        for j in jobs:
            try:
                session.delete(j)
            except Exception:
                pass

        if p:
            try:
                session.delete(p)
            except Exception:
                pass

    # Also clean up any NEW library assets created during this doctor run.
    # We do this outside the transaction above to keep it resilient.
    with session_scope() as session:
        lib_new = session.exec(
            select(Asset)
            .where(Asset.tag == "library")
            .where(Asset.created_at >= started_at)
        ).all()
        for a in lib_new:
            try:
                _delete_asset_file(a)
            except Exception:
                pass
            try:
                session.delete(a)
            except Exception:
                pass


@dataclass(frozen=True)
class _LlmStatus:
    ok: bool
    detail: str = ""
    provider_type: str = ""


def _check_llm() -> _LlmStatus:
    from app.llm_service import get_default_provider, get_api_key, has_api_key

    with session_scope() as session:
        p = get_default_provider(session)
        if not p or p.id is None or not p.enabled:
            return _LlmStatus(ok=False, detail="未设置默认大模型 Provider")

        provider_type = str(p.type or "")
        base_url = str(p.base_url or "").strip()
        model = str(p.default_model or "").strip()
        if not base_url or not model:
            return _LlmStatus(ok=False, provider_type=provider_type, detail="LLM base_url/model 未配置")

        key = ""
        if provider_type == "openai_compat":
            if not has_api_key(session, int(p.id)):
                return _LlmStatus(ok=False, provider_type=provider_type, detail="未设置 LLM API Key")
            key = get_api_key(session, int(p.id))

    # Do a minimal real call (costs tiny tokens on openai_compat).
    try:
        messages = [
            LlmChatMessage(role="system", content="Return STRICT JSON only."),
            LlmChatMessage(role="user", content='Return JSON: {"ok": true}'),
        ]
        if provider_type == "ollama":
            obj = ollama_chat_json(base_url=base_url, model=model, messages=messages)
        else:
            obj = openai_compat_chat_json(base_url=base_url, api_key=key, model=model, messages=messages)
        if not isinstance(obj, dict):
            return _LlmStatus(ok=False, provider_type=provider_type, detail="LLM 返回非 JSON 对象")
    except Exception as e:
        return _LlmStatus(ok=False, provider_type=provider_type, detail=f"LLM 调用失败：{e}")

    return _LlmStatus(ok=True, provider_type=provider_type, detail="正常")


def _check_media() -> tuple[bool, str, str]:
    """Return (ok, provider, detail). Requires at least one provider key AND a successful search."""

    providers = ["pexels", "pixabay"]
    with session_scope() as session:
        for p in providers:
            if not has_media_api_key(session, p):
                continue
            key = get_media_api_key(session, p)
            if not key:
                continue
            try:
                items = search_web_media(provider=p, kind="image", query="city skyline", limit=3, api_key=key)
                if items:
                    return (True, p, "正常")
            except Exception as e:
                return (False, p, f"{p} 搜索失败：{e}")
        return (False, "", "未配置 Pexels/Pixabay API Key（混剪需要至少一个）")


def run_mix_smoke_check(*, require_llm: bool = True, require_media: bool = True) -> DoctorOut:
    """Run an end-to-end smoke check focused on MIX workflow.

    Policy:
    - If require_llm=True: must have a working default LLM provider.
    - If require_media=True: must have at least one working media provider (Pexels/Pixabay).
    """

    started_at_dt = now_utc()
    started_at = _now_iso()
    t0 = time.time()
    items: list[DoctorItemOut] = []
    ok_all = True

    # 0) Web UI build (avoid low-level page errors)
    try:
        from app.settings import settings

        idx = settings.web_dist_dir / "index.html"
        ui_dir = settings.web_dist_dir / "ui"
        web_ok = bool(idx.exists() and ui_dir.exists())
        if not web_ok:
            ok_all = False
        items.append(
            DoctorItemOut(
                ok=web_ok,
                name="web_ui",
                status="已构建" if web_ok else "未构建",
                detail=str(idx) if idx.exists() else str(idx),
                hint="先在 apps/web 运行 npm install && npm run build 构建前端" if not web_ok else None,
            )
        )
    except Exception as e:
        ok_all = False
        items.append(DoctorItemOut(ok=False, name="web_ui", status="检查失败", detail=str(e)[:300]))

    # 1) LLM
    llm = _check_llm()
    llm_ok = bool(llm.ok)
    if require_llm and not llm_ok:
        ok_all = False
    items.append(
        DoctorItemOut(
            ok=llm_ok,
            name="llm",
            status=llm.detail or ("正常" if llm_ok else "异常"),
            detail=(f"type={llm.provider_type}" if llm.provider_type else None),
            hint="请在 设置 -> 大模型 配置默认 Provider 与 Key" if not llm_ok else None,
        )
    )

    # 2) Media providers
    media_ok, media_provider, media_detail = _check_media()
    if require_media and not media_ok:
        ok_all = False
    items.append(
        DoctorItemOut(
            ok=media_ok,
            name="media",
            status=media_detail or ("正常" if media_ok else "异常"),
            detail=(f"provider={media_provider}" if media_provider else None),
            hint="请在 设置 -> 素材来源 配置 Pexels/Pixabay API Key" if not media_ok else None,
        )
    )

    project_id: int | None = None
    try:
        # If prerequisites failed, skip heavy steps.
        if require_llm and not llm_ok:
            raise RuntimeError("LLM not ready")
        if require_media and not media_ok:
            raise RuntimeError("Media provider not ready")

        # 3) Create a tiny doctor project (3 scenes) and run: autofill -> render
        with session_scope() as session:
            pack = session.exec(select(ChannelPack).order_by(ChannelPack.key)).first()
            pack_key = (pack.key if pack else "history")
            p = Project(
                title=f"__doctor__mix_smoke_{now_utc().strftime('%Y%m%d_%H%M%S')}",
                workflow="mix",
                channel_key=str(pack_key),
                status="draft",
                script="doctor smoke",
            )
            session.add(p)
            session.flush()
            session.refresh(p)
            project_id = int(p.id)

            scenes = [
                (1, "city skyline at night", "city skyline night"),
                (2, "office people working", "office working"),
                (3, "nature river sunrise", "river sunrise"),
            ]
            for idx, nar, mq in scenes:
                session.add(
                    Scene(
                        project_id=project_id,
                        idx=int(idx),
                        narration=nar,
                        media_query=mq,
                        image_prompt="",
                        image_negative="",
                        duration_sec=2.0,
                        status="pending",
                    )
                )

        # 3a) autofill
        from app.tasks_entries import autofill_media, render_video

        j1 = create_job("autofill_media", project_id, message="doctor", payload={"project_id": project_id})
        # Huey tasks are enqueued by default; for doctor we need a true local smoke run.
        autofill_media.call_local(int(j1.id), project_id, prefer="video", keep_running=False)
        st, _prog, msg = _job_snapshot(int(j1.id))

        with session_scope() as session:
            scenes_now = session.exec(select(Scene).where(Scene.project_id == project_id)).all()
            filled = len([s for s in scenes_now if s.image_asset_id])

        fill_ok = st == "done" and filled >= 1
        if not fill_ok:
            ok_all = False
        items.append(
            DoctorItemOut(
                ok=fill_ok,
                name="autofill",
                status=f"{st} ({filled}/{len(scenes_now)})",
                detail=(msg[:260] if msg else None),
                hint="素材匹配失败：检查网络、API Key、或降低镜头关键词抽象程度" if not fill_ok else None,
            )
        )

        # 3b) render final (short)
        overrides = {"width": 360, "height": 640, "motion_zoom": 0.02, "transition": "none"}
        j2 = create_job(
            "render",
            project_id,
            message="doctor",
            payload={"project_id": project_id, "overrides": overrides},
        )
        render_video.call_local(int(j2.id), project_id)
        st2, _prog2, msg2 = _job_snapshot(int(j2.id))

        # Verify an export video exists on disk
        from app.project_paths import asset_disk_path

        out_ok = False
        out_path = ""
        with session_scope() as session:
            vids = session.exec(
                select(Asset)
                .where(Asset.project_id == project_id)
                .where(Asset.kind == "video")
                .where(Asset.tag == "export")
                .order_by(Asset.created_at.desc())
            ).all()
            if vids:
                a = vids[0]
                resolved = asset_disk_path(str(a.rel_path or ""), is_export=True)
                out_path = str(resolved)
                try:
                    out_ok = resolved.exists() and resolved.is_file()
                except Exception:
                    out_ok = False
        render_ok = st2 == "done" and out_ok
        if not render_ok:
            ok_all = False
        items.append(
            DoctorItemOut(
                ok=render_ok,
                name="render",
                status=st2,
                detail=(out_path or (msg2[:260] if msg2 else None)),
                hint="渲染失败：优先检查 ffmpeg、写入权限、以及杀毒软件拦截" if not render_ok else None,
            )
        )
    except Exception as e:
        ok_all = False
        items.append(
            DoctorItemOut(
                ok=False,
                name="pipeline",
                status="failed",
                detail=str(e)[:500],
                hint="先修复上面的 LLM/素材来源配置，再重试 doctor" if ("not ready" in str(e).lower()) else None,
            )
        )
    finally:
        if project_id is not None:
            try:
                _cleanup_doctor_project(project_id=project_id, started_at=started_at_dt)
            except Exception:
                pass

    finished_at = _now_iso()
    dur_ms = int((time.time() - t0) * 1000)
    return DoctorOut(ok=bool(ok_all), started_at=started_at, finished_at=finished_at, duration_ms=dur_ms, items=items)
