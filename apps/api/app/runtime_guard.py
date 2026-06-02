from __future__ import annotations

import os
from pathlib import Path


_GETUID_IS_FALLBACK = not hasattr(os, "getuid")
_GETGID_IS_FALLBACK = not hasattr(os, "getgid")


if not hasattr(os, "getuid"):
    def _fallback_getuid() -> int:
        return 0

    os.getuid = _fallback_getuid  # type: ignore[attr-defined]

if not hasattr(os, "getgid"):
    def _fallback_getgid() -> int:
        return 0

    os.getgid = _fallback_getgid  # type: ignore[attr-defined]


def enforce_non_root_runtime(*, data_dir: Path, role: str) -> None:
    """Block accidental root startup against the shared runtime data dir.

    systemd production services already run as the dedicated `chengpian` user.
    The main risk comes from operators manually starting API/worker from a root
    shell, which leaves root-owned files under `data/` and later breaks cleanup.
    """

    if _GETUID_IS_FALLBACK and getattr(os, "getuid", None) is _fallback_getuid:
        return

    if os.name == "nt":
        return

    try:
        uid = os.getuid()
    except Exception:
        return
    if uid != 0:
        return

    allow_root = os.environ.get("CHENGPIAN_ALLOW_ROOT_RUNTIME", "0").strip().lower() in ("1", "true", "yes")
    if allow_root:
        return

    target = Path(data_dir).resolve()
    raise RuntimeError(
        f"拒绝以 root 身份启动 {role}：当前运行目录是 {target}。"
        "请改用 chengpian 用户通过 systemd 启动，"
        "或仅在明确知晓风险时设置 CHENGPIAN_ALLOW_ROOT_RUNTIME=1。"
    )
