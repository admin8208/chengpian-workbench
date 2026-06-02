from pathlib import Path
import os

if os.name != "nt":
    import grp
    import pwd
else:
    class _MissingPwdModule:
        def getpwnam(self, _name: str):
            raise OSError("pwd unavailable on Windows")

    class _MissingGrpModule:
        def getgrnam(self, _name: str):
            raise OSError("grp unavailable on Windows")

    grp = _MissingGrpModule()
    pwd = _MissingPwdModule()

if not hasattr(os, "chown"):
    def _missing_chown(_path, _uid, _gid) -> None:
        return None

    os.chown = _missing_chown  # type: ignore[attr-defined]

from app.settings import settings


def projects_root_path() -> Path:
    return (settings.data_dir / "projects").resolve()


def ensure_projects_root_dir() -> Path:
    root = projects_root_path()
    root.mkdir(parents=True, exist_ok=True)
    _normalize_runtime_owner(root)
    return root


def projects_root_dir() -> Path:
    return ensure_projects_root_dir()


def project_root_path(project_id: int) -> Path:
    return projects_root_path() / f"project_{int(project_id)}"


def ensure_project_root_dir(project_id: int) -> Path:
    root = project_root_path(project_id)
    root.mkdir(parents=True, exist_ok=True)
    _normalize_runtime_owner(root)
    return root


def project_root_dir(project_id: int) -> Path:
    return ensure_project_root_dir(project_id)


def _ensure_project_child_dir(project_id: int, name: str) -> Path:
    p = ensure_project_root_dir(project_id) / str(name)
    p.mkdir(parents=True, exist_ok=True)
    _normalize_runtime_owner(p)
    return p


def _runtime_uid_gid() -> tuple[int, int] | None:
    if pwd is None or grp is None:
        return None
    try:
        return pwd.getpwnam("chengpian").pw_uid, grp.getgrnam("chengpian").gr_gid
    except Exception:
        return None


def _normalize_runtime_owner(path: Path) -> None:
    ids = _runtime_uid_gid()
    if not ids:
        return
    uid, gid = ids
    try:
        st = path.stat()
    except Exception:
        return
    if st.st_uid == uid and st.st_gid == gid:
        return
    try:
        os.chown(path, uid, gid)
    except PermissionError:
        # 非特权进程只保证自身能继续工作；权限巡检会提示异常属主。
        return
    except Exception:
        return


def project_exports_path(project_id: int) -> Path:
    return project_root_path(project_id) / "exports"


def project_exports_dir(project_id: int) -> Path:
    return _ensure_project_child_dir(project_id, "exports")


def project_audio_path(project_id: int) -> Path:
    return project_root_path(project_id) / "audio"


def project_audio_dir(project_id: int) -> Path:
    return _ensure_project_child_dir(project_id, "audio")


def project_subtitles_path(project_id: int) -> Path:
    return project_root_path(project_id) / "subtitles"


def project_subtitles_dir(project_id: int) -> Path:
    return _ensure_project_child_dir(project_id, "subtitles")


def project_generated_path(project_id: int) -> Path:
    return project_root_path(project_id) / "generated"


def project_generated_dir(project_id: int) -> Path:
    return _ensure_project_child_dir(project_id, "generated")


def project_uploads_path(project_id: int) -> Path:
    return project_root_path(project_id) / "uploads"


def project_uploads_dir(project_id: int) -> Path:
    return _ensure_project_child_dir(project_id, "uploads")


def project_rolecards_path(project_id: int) -> Path:
    return project_root_path(project_id) / "rolecards"


def project_rolecards_dir(project_id: int) -> Path:
    return _ensure_project_child_dir(project_id, "rolecards")


def project_imported_path(project_id: int) -> Path:
    return project_root_path(project_id) / "imported"


def project_imported_dir(project_id: int) -> Path:
    return _ensure_project_child_dir(project_id, "imported")


def project_tmp_path(project_id: int) -> Path:
    return project_root_path(project_id) / "tmp"


def project_tmp_dir(project_id: int) -> Path:
    return _ensure_project_child_dir(project_id, "tmp")


def rel_to_projects_root(path: Path) -> str:
    return str(path.resolve().relative_to(projects_root_path())).replace("\\", "/")


def project_public_url(rel_path: str) -> str:
    return f"/projects/{str(rel_path or '').lstrip('/')}"


def project_path_from_rel(rel_path: str) -> Path:
    return (projects_root_path() / str(rel_path or "").lstrip("/")).resolve()


def asset_disk_path(rel_path: str, *, is_export: bool = False) -> Path:
    rel = str(rel_path or "").lstrip("/")
    if rel.startswith("project_"):
        return project_path_from_rel(rel)
    base = settings.exports_dir if is_export else settings.assets_dir
    return (base / rel).resolve()


def project_root_specs(project_id: int) -> list[tuple[Path, str]]:
    pid = int(project_id)
    return [
        (projects_root_path(), f"project_{pid}"),
    ]
