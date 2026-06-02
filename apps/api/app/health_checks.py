
import os
import shutil
import subprocess
from pathlib import Path

if os.name != "nt":
    import pwd
    import grp
else:
    class _MissingPwdModule:
        def getpwnam(self, _name: str):
            raise OSError("pwd unavailable on Windows")

    class _MissingGrpModule:
        def getgrnam(self, _name: str):
            raise OSError("grp unavailable on Windows")

    pwd = _MissingPwdModule()
    grp = _MissingGrpModule()

import imageio_ffmpeg
from sqlalchemy import func, select

from app.db import session_scope
from app.huey_app import huey
from app.jobs import huey_queue_table_count, worker_heartbeat_age_seconds, worker_heartbeat_alive
from app.job_control import job_lease_is_stale, worker_pid_exists
from app.models import Job
from app.schemas import HealthComponentOut
from app.network_checks import https_probe, tts_proxy_summary
from app.settings import settings
from app.modules.tts.offline import offline_tts_status
from app.modules.tts.catalog import DEFAULT_VOICE_ID
from app.modules.tts.service import edge_synthesis_cached_state, edge_synthesis_probe_cached


def check_storage() -> HealthComponentOut:
    try:
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        usage = shutil.disk_usage(str(settings.data_dir))
        free_gb = usage.free / (1024**3)
        return HealthComponentOut(
            ok=True,
            status=f"剩余 {free_gb:.1f} GB",
        )
    except Exception as e:
        return HealthComponentOut(ok=False, status="错误", detail=str(e))


def check_runtime_permissions() -> HealthComponentOut:
    try:
        expected_uid = pwd.getpwnam("chengpian").pw_uid
        expected_gid = grp.getgrnam("chengpian").gr_gid
    except Exception:
        return HealthComponentOut(
            ok=True,
            status="Windows 本机",
            detail="Windows 不使用 Linux chengpian 用户属主检查",
        )
    try:
        roots = [
            settings.data_dir,
            settings.assets_dir,
            settings.exports_dir,
            settings.huey_storage_dir,
            settings.data_dir / "projects",
        ]
        issues: list[str] = []
        checked: list[Path] = []
        base_dir = settings.data_dir.resolve()

        def _display_path(path: Path) -> str:
            try:
                return str(path.resolve().relative_to(base_dir.parent)).replace("\\", "/")
            except Exception:
                return str(path).replace("\\", "/")

        def _check_child(path: Path) -> None:
            st_child = path.stat()
            if st_child.st_uid != expected_uid or st_child.st_gid != expected_gid:
                issues.append(f"{_display_path(path)}: 属主 {st_child.st_uid}:{st_child.st_gid}")

        for root in roots:
            checked.append(root)
            if not root.exists():
                continue
            st = root.stat()
            if st.st_uid != expected_uid or st.st_gid != expected_gid:
                issues.append(f"{_display_path(root)}: 属主 {st.st_uid}:{st.st_gid}")
                continue
            if not root.is_dir():
                continue
            for child in root.iterdir():
                name = child.name
                if root == settings.data_dir and name in {"archive", "postgres_clean_migrated_backup_20260503"}:
                    continue
                _check_child(child)
                if root == settings.data_dir / "projects" and child.is_dir():
                    try:
                        for nested in child.rglob("*"):
                            _check_child(nested)
                            if len(issues) >= 12:
                                break
                    except Exception:
                        pass
                if len(issues) >= 12:
                    break
            if len(issues) >= 12:
                break
        if issues:
            sample = "；".join(issues[:6])
            return HealthComponentOut(
                ok=False,
                status="属主异常",
                detail=f"检测到运行目录存在非 chengpian 属主条目：{sample}",
                hint="建议只用 chengpian 用户运行 API/Worker，并避免 root 或容器身份直接写入 data/ 运行目录。",
            )
        return HealthComponentOut(ok=True, status="正常", detail=f"已检查 {len(checked)} 个运行目录，属主一致")
    except Exception as e:
        return HealthComponentOut(ok=False, status="错误", detail=str(e)[:300])


def check_huey_queue() -> HealthComponentOut:
    try:
        pending = huey_queue_table_count()
        scheduled = int(huey.scheduled_count())
        return HealthComponentOut(ok=True, status="正常", detail=f"Redis queue pending={pending if pending is not None else 'unknown'} · scheduled={scheduled}")
    except Exception as e:
        return HealthComponentOut(ok=False, status="错误", detail=str(e)[:300])


def check_worker() -> HealthComponentOut:
    try:
        age = worker_heartbeat_age_seconds()
        alive = worker_heartbeat_alive()
        pending = huey_queue_table_count()
        stale_running = 0
        missing_pid = 0
        with session_scope() as session:
            running_jobs = session.exec(select(Job).where(Job.status == "running")).all()
            queued_row = session.exec(
                select(func.count())
                .select_from(Job)
                .where(Job.status == "queued")
            ).one()
        for job in running_jobs:
            worker_pid = int(getattr(job, "worker_pid", 0) or 0)
            if worker_pid > 0 and not worker_pid_exists(worker_pid):
                missing_pid += 1
            if job_lease_is_stale(job):
                stale_running += 1
        if isinstance(queued_row, (tuple, list)):
            queued_count = int(queued_row[0] or 0)
        else:
            try:
                queued_count = int(getattr(queued_row, "count_1", queued_row) or 0)
            except Exception:
                queued_count = 0
        if alive and stale_running == 0 and missing_pid == 0:
            return HealthComponentOut(
                ok=True,
                status="在线",
                detail=f"worker 心跳正常（约 {int(age or 0)} 秒前）· Redis pending {pending if pending is not None else 'unknown'} 个 · queued 任务 {queued_count} 个",
            )
        if stale_running > 0 or missing_pid > 0:
            return HealthComponentOut(
                ok=False,
                status="异常",
                detail=(
                    f"检测到陈旧运行任务 {stale_running} 个 · 丢失 worker 进程租约 {missing_pid} 个 "
                    f"· Redis pending {pending if pending is not None else 'unknown'} 个 · queued 任务 {queued_count} 个"
                ),
                hint="建议先清理陈旧任务或重启 worker 后再继续生成。",
            )
        return HealthComponentOut(
            ok=False,
            status="离线",
            detail=f"最近未检测到 worker 心跳 · Redis pending {pending if pending is not None else 'unknown'} 个 · queued 任务 {queued_count} 个",
            hint="如果项目长期显示排队中，优先检查 chengpian-worker.service、redis-server.service 是否运行，以及 PostgreSQL/Redis 连接是否正常。",
        )
    except Exception as e:
        return HealthComponentOut(ok=False, status="错误", detail=str(e)[:300])


def check_ffmpeg() -> HealthComponentOut:
    try:
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        p = subprocess.run([exe, "-version"], capture_output=True, text=True, timeout=5)
        if p.returncode != 0:
            return HealthComponentOut(ok=False, status="ffmpeg 异常", detail=p.stderr[:300])
        head = (p.stdout or "").splitlines()[0] if p.stdout else "ffmpeg"
        return HealthComponentOut(ok=True, status="已安装", detail=head)
    except Exception as e:
        return HealthComponentOut(ok=False, status="未检测到 ffmpeg", detail=str(e))


def check_edge_tts(*, probe: bool = False) -> HealthComponentOut:
    try:
        proxy = tts_proxy_summary()
        if probe:
            ok, detail, checked = edge_synthesis_probe_cached(
                voice="zh-CN-XiaoxiaoNeural",
                rate="+0%",
                timeout_s=8,
                ttl_s=180,
                force=True,
            )
        else:
            checked, ok, detail = edge_synthesis_cached_state(
                voice="zh-CN-XiaoxiaoNeural",
                rate="+0%",
                timeout_s=8,
                ttl_s=180,
            )
        if not checked:
            return HealthComponentOut(
                ok=False,
                status="不可用",
                detail=(f"在线配音自动检测未完成。当前 TTS 代理：{proxy.get('proxy') or '未检测到'}"),
                hint="如果离线配音正常，就不会影响生成视频；如需在线配音，请稍后刷新再看。",
            )
        if ok:
            return HealthComponentOut(ok=True, status="可用", detail=(detail or "最近一次在线配音检测通过") + (f" · TTS 代理：{proxy.get('proxy')}" if proxy.get('proxy') else ""))
        return HealthComponentOut(
            ok=False,
            status="不可用",
            detail=(detail or "在线配音当前不可用") + (f" · TTS 代理：{proxy.get('proxy')}" if proxy.get('proxy') else " · 未检测到 TTS 代理"),
            hint="Edge TTS 合成需要访问微软服务（国内环境可能需要代理/VPN）。如果离线配音正常，则不影响出片。",
        )
    except Exception as e:
        return HealthComponentOut(
            ok=False,
            status="不可用",
            detail=str(e)[:300],
            hint="Edge TTS 合成需要访问微软服务（国内环境可能需要代理/VPN）。如果离线配音正常，则不影响出片。",
        )


def check_offline_tts() -> HealthComponentOut:
    try:
        st = offline_tts_status(voice_id=DEFAULT_VOICE_ID, probe=True)
        if not st.installed:
            return HealthComponentOut(
                ok=False,
                status="未安装",
                hint="建议在 设置->配音 一键安装离线中文配音（推荐，Edge 不通也能生成视频）。",
            )
        if not st.ok:
            return HealthComponentOut(
                ok=False,
                status="已安装但不可用",
                detail=st.detail,
                hint="可尝试重新安装离线配音，或检查是否被杀软拦截。",
            )
        return HealthComponentOut(ok=True, status="正常")
    except Exception as e:
        return HealthComponentOut(ok=False, status="错误", detail=str(e)[:300])


def check_online_base() -> HealthComponentOut:
    proxy = tts_proxy_summary()
    ok, detail = https_probe("https://speech.platform.bing.com/consumer/speech/synthesize/readaloud/voices/list?trustedclienttoken=test", timeout_s=8)
    if ok:
        return HealthComponentOut(ok=True, status="可访问", detail=(f"在线配音基础链路正常 · TTS 代理：{proxy.get('proxy') or '未检测到'}"))
    return HealthComponentOut(ok=False, status="不可访问", detail=(f"{detail} · TTS 代理：{proxy.get('proxy') or '未检测到'}"), hint="先确认运行 API/Worker 的机器能访问微软 TTS 服务；如需代理，请配置 CHENGPIAN_TTS_PROXY。")
