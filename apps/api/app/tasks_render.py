import json
import sqlite3
import shutil
import time
from pathlib import Path

from loguru import logger
from sqlalchemy.exc import OperationalError
from sqlmodel import select

from app.db import session_scope
from app.models import Asset, Scene
from app.project_paths import asset_disk_path, rel_to_projects_root
from app.settings import settings
from app.api_common import register_project_tts_cache_refs


def rel_to_dir(p: Path, base: Path) -> str:
    return str(p.resolve().relative_to(base)).replace("\\", "/")


def score_candidate_video(p: Path, meta: dict) -> int:
    score = int(p.stat().st_size)
    if not bool(meta.get("subtitle_degraded")):
        score += 2_000_000_000
    sub_mode = str(meta.get("subtitle_mode") or "")
    if sub_mode.startswith("burned"):
        score += 500_000_000
    elif sub_mode == "audio_only":
        score -= 400_000_000
    if bool(meta.get("subtitle_retry_used")):
        score -= 25_000_000
    try:
        w, h = int(meta.get("width", 0) or 0), int(meta.get("height", 0) or 0)
        pixels = w * h
        if pixels >= 1920 * 1080:
            score += 300_000_000
        elif pixels >= 1280 * 720:
            score += 150_000_000
        elif pixels > 0 and pixels < 720 * 480:
            score -= 50_000_000
    except Exception:
        pass
    if str(meta.get("transition", "")).lower() == "crossfade":
        score += 100_000_000
    try:
        mz = float(meta.get("motion_zoom", 0) or 0)
        if mz > 0.05:
            score += 50_000_000
        elif mz == 0 and not sub_mode.startswith("burned"):
            score -= 10_000_000
    except Exception:
        pass
    return score


def subtitle_has_visible_cues(p: Path) -> bool:
    try:
        if (not p.exists()) or p.stat().st_size <= 0:
            return False
        txt = p.read_text(encoding="utf-8", errors="ignore")
        if not txt.strip():
            return False
        lines = [ln.strip() for ln in txt.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
        for i, ln in enumerate(lines):
            if "-->" not in ln:
                continue
            j = i + 1
            while j < len(lines) and lines[j] != "":
                t = lines[j].strip()
                if t and (not t.isdigit()):
                    return True
                j += 1
        return False
    except Exception:
        return False


def finalize_render_outputs(
    *,
    pid: int,
    tag: str,
    ts: str,
    out_dir: Path,
    out_file: Path,
    out_tmp: Path,
    audio_path: Path,
    srt_path: Path,
    candidate_batch_id: str | None,
    render_job_id: int,
    render_token: str,
    render_meta: dict | None = None,
    is_generated_render_rel_path,
    cleanup_project_intermediate_artifacts,
) -> tuple[Path, Path | None]:
    history_path: Path | None = None
    cleanup_warnings: list[str] = []

    def _storage_rel(path: Path) -> str:
        if not path.exists():
            return ""
        resolved = path.resolve()
        try:
            return str(resolved.relative_to(settings.assets_dir.resolve())).replace("\\", "/")
        except Exception:
            return rel_to_projects_root(resolved)

    current_audio_rel = _storage_rel(audio_path)
    current_subtitle_rel = _storage_rel(srt_path)

    def _warn(msg: str) -> None:
        cleanup_warnings.append(msg)
        logger.warning(msg)

    try:
        if out_tmp.exists() and out_tmp.stat().st_size > 0:
            if tag == "export":
                try:
                    if out_file.exists() and out_file.stat().st_size > 0:
                        hist_dir = out_dir / "history"
                        hist_dir.mkdir(parents=True, exist_ok=True)
                        history_path = hist_dir / f"final_{ts}.mp4"
                        try:
                            shutil.copyfile(out_file, history_path)
                        except Exception as e:
                            _warn(f"render history copy failed for project {pid}: {e}")
                            history_path = None
                except Exception as e:
                    _warn(f"render history prepare failed for project {pid}: {e}")
                    history_path = None
                try:
                    try:
                        if out_file.exists():
                            out_file.unlink(missing_ok=True)
                    except Exception as e:
                        _warn(f"render final cleanup failed for project {pid}: {e}")
                    out_tmp.replace(out_file)
                except Exception as e:
                    _warn(f"render final replace fallback used for project {pid}: {e}")
                    out_file = out_tmp
            else:
                try:
                    out_tmp.replace(out_file)
                except Exception as e:
                    _warn(f"render candidate replace fallback used for project {pid}: {e}")
                    out_file = out_tmp
    except Exception as e:
        _warn(f"render output finalize pre-db failed for project {pid}: {e}")
    try:
        for p in out_dir.glob("*_tmp_*.mp4"):
            try:
                p.unlink(missing_ok=True)
            except Exception as e:
                _warn(f"render temp cleanup failed for project {pid}: {e}")
        cand_dir = out_dir / "candidates"
        if cand_dir.exists():
            for p in cand_dir.glob("*_tmp_*.mp4"):
                try:
                    p.unlink(missing_ok=True)
                except Exception as e:
                    _warn(f"render candidate temp cleanup failed for project {pid}: {e}")
    except Exception as e:
        _warn(f"render temp glob cleanup failed for project {pid}: {e}")
    def _write_render_assets() -> None:
        with session_scope() as session:
            for cleanup_tag in ("voice", "subtitle", "voice_generated", "subtitle_generated"):
                olds = session.exec(select(Asset).where(Asset.project_id == pid).where(Asset.tag == cleanup_tag)).all()
                for old in olds:
                    try:
                        old_rel = str(getattr(old, "rel_path", "") or "").strip()
                        if cleanup_tag in ("voice", "voice_generated") and old_rel == current_audio_rel:
                            continue
                        if cleanup_tag in ("subtitle", "subtitle_generated") and old_rel == current_subtitle_rel:
                            continue
                        if old.rel_path and is_generated_render_rel_path(pid, old.rel_path):
                            old_path = asset_disk_path(str(old.rel_path), is_export=False)
                            if old_path.exists() and old_path.is_file():
                                old_path.unlink(missing_ok=True)
                        session.delete(old)
                    except Exception as e:
                        _warn(f"render asset cleanup failed for project {pid}, tag={cleanup_tag}: {e}")
            if audio_path.exists():
                audio_meta = json.dumps({"render_job_id": int(render_job_id), "render_token": str(render_token)}, ensure_ascii=True)
                try:
                    register_project_tts_cache_refs(pid, [current_audio_rel])
                except Exception:
                    pass
                exists = session.exec(select(Asset).where(Asset.project_id == pid).where(Asset.tag == "voice_generated").where(Asset.rel_path == current_audio_rel)).first()
                if exists:
                    exists.meta_json = audio_meta
                    session.add(exists)
                else:
                    session.add(Asset(kind="audio", rel_path=current_audio_rel, mime="audio/mpeg", project_id=pid, tag="voice_generated", meta_json=audio_meta))
            if srt_path.exists():
                subtitle_meta = json.dumps({"render_job_id": int(render_job_id), "render_token": str(render_token)}, ensure_ascii=True)
                try:
                    register_project_tts_cache_refs(pid, [current_subtitle_rel])
                except Exception:
                    pass
                exists = session.exec(select(Asset).where(Asset.project_id == pid).where(Asset.tag == "subtitle_generated").where(Asset.rel_path == current_subtitle_rel)).first()
                if exists:
                    exists.meta_json = subtitle_meta
                    session.add(exists)
                else:
                    session.add(Asset(kind="other", rel_path=current_subtitle_rel, mime="text/plain", project_id=pid, tag="subtitle_generated", meta_json=subtitle_meta))
            if tag == "export":
                for o in session.exec(select(Asset).where(Asset.project_id == pid).where(Asset.kind == "video").where(Asset.tag == "export")).all():
                    try:
                        session.delete(o)
                    except Exception as e:
                        _warn(f"render export record cleanup failed for project {pid}: {e}")
            if out_file.exists() and out_file.stat().st_size > 0:
                meta_json = "{}"
                if render_meta:
                    try:
                        meta_obj: dict[str, object] = {"render_job_id": int(render_job_id), "render_token": str(render_token)}
                        if isinstance(render_meta, dict):
                            meta_obj.update(render_meta)
                        if cleanup_warnings:
                            meta_obj["cleanup_warnings"] = cleanup_warnings[:8]
                        meta_json = json.dumps(meta_obj, ensure_ascii=True)
                    except Exception as e:
                        _warn(f"render meta encode failed for project {pid}: {e}")
                        meta_json = "{}"
                session.add(Asset(kind="video", rel_path=rel_to_projects_root(out_file), mime="video/mp4", project_id=pid, tag=("export" if tag == "export" else tag), meta_json=meta_json))

    last_db_error: Exception | None = None
    for attempt in range(4):
        try:
            _write_render_assets()
            last_db_error = None
            break
        except (OperationalError, sqlite3.OperationalError) as e:
            low = str(e).lower()
            if "database is locked" not in low:
                raise
            last_db_error = e
            time.sleep(0.2 * (attempt + 1))
    if last_db_error is not None:
        raise last_db_error
    if str(tag or "").strip().lower() == "export":
        try:
            cleanup_project_intermediate_artifacts(int(pid))
        except Exception as e:
            _warn(f"render final intermediate cleanup failed for project {pid}: {e}")
    return out_file, history_path
