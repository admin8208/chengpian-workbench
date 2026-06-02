import shutil
import stat
from pathlib import Path

from app.project_paths import project_root_specs
from app.services.tts_cache_registry import cleanup_project_tts_cache_refs


def safe_unlink(base: Path, rel: str) -> None:
    if not rel:
        return
    path = (base / rel.lstrip("/")).resolve()
    root = base.resolve()
    if root not in path.parents and path != root:
        return
    try:
        if path.exists() and path.is_file():
            path.unlink()
    except Exception:
        pass


def safe_rmtree(base: Path, rel: str) -> None:
    if not rel:
        return
    path = (base / rel.lstrip("/")).resolve()
    root = base.resolve()
    if root not in path.parents and path != root:
        return
    try:
        if path.exists() and path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
    except Exception:
        pass


def project_storage_dir_specs(project_id: int) -> list[tuple[Path, str]]:
    return project_root_specs(project_id)


def _safe_join(base: Path, rel: str) -> Path:
    path = (base / rel.lstrip("/")).resolve()
    root = base.resolve()
    if root not in path.parents and path != root:
        raise RuntimeError("非法路径")
    return path


def _path_issue_hint(path: Path) -> str:
    try:
        st = path.stat()
        mode = stat.S_IMODE(st.st_mode)
        return f" [uid={int(st.st_uid)} gid={int(st.st_gid)} mode={oct(mode)}]"
    except Exception:
        return ""


def remove_project_storage_strict(project_id: int, *, extra_file_refs: list[tuple[Path, str]] | None = None) -> list[str]:
    leftovers: list[str] = []
    for base, rel in extra_file_refs or []:
        try:
            path = _safe_join(base, rel)
            if path.exists() and path.is_file():
                path.unlink()
            if path.exists():
                leftovers.append(f"{str(path)}{_path_issue_hint(path)}")
        except Exception:
            target = Path(str(base)) / str(rel).lstrip("/")
            leftovers.append(f"{str(target)}{_path_issue_hint(target)}")
    for base, rel in project_storage_dir_specs(project_id):
        try:
            path = _safe_join(base, rel)
            if path.exists() and path.is_dir():
                shutil.rmtree(path)
            if path.exists():
                leftovers.append(f"{str(path)}{_path_issue_hint(path)}")
        except Exception:
            target = Path(str(base)) / str(rel).lstrip("/")
            leftovers.append(f"{str(target)}{_path_issue_hint(target)}")
    return leftovers


def project_storage_leftovers(project_id: int) -> list[str]:
    leftovers: list[str] = []
    for base, rel in project_storage_dir_specs(project_id):
        try:
            path = _safe_join(base, rel)
            if path.exists():
                leftovers.append(str(path))
        except Exception:
            leftovers.append(f"{str(base)}/{rel}")
    return leftovers


def ensure_project_storage_clean(project_id: int, *, extra_file_refs: list[tuple[Path, str]] | None = None) -> list[str]:
    remove_project_storage_strict(project_id, extra_file_refs=extra_file_refs)
    leftovers = project_storage_leftovers(project_id)
    leftovers.extend(cleanup_project_tts_cache_refs(project_id))
    return leftovers
